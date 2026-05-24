"""
CDP协议客户端模块

通过WebSocket连接Chrome DevTools Protocol，实现：
- 发送CDP命令并接收响应
- 订阅和接收CDP事件
- 异步消息ID管理
- 自动重连机制
- 超时处理

支持两种WebSocket实现：
1. websockets库（推荐，通过pip install websockets安装）
2. 内置的socket+ssl回退实现（功能有限）
"""

import asyncio
import hashlib
import json
import logging
import os
import socket
import ssl
import struct
import sys
import time
import urllib.parse
from base64 import b64encode
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from .config import Config
from .utils import safe_json_loads, safe_json_dumps, timestamp_ms

logger = logging.getLogger(__name__)


# ============================================================
# WebSocket帧操作（用于内置回退实现）
# ============================================================

# WebSocket操作码
WS_OPCODE_TEXT = 0x1
WS_OPCODE_BINARY = 0x2
WS_OPCODE_CLOSE = 0x8
WS_OPCODE_PING = 0x9
WS_OPCODE_PONG = 0xA


class WebSocketFrame:
    """WebSocket帧解析和构建"""

    @staticmethod
    def build_frame(
        opcode: int, payload: bytes, mask: bool = True
    ) -> bytes:
        """
        构建WebSocket数据帧

        Args:
            opcode: 操作码
            payload: 载荷数据
            mask: 是否使用掩码（客户端必须使用）

        Returns:
            完整的WebSocket帧字节
        """
        frame = bytearray()
        # FIN + opcode
        frame.append(0x80 | opcode)

        length = len(payload)
        if length < 126:
            frame.append(0x80 | length if mask else length)
        elif length < 65536:
            frame.append(0x80 | 126 if mask else 126)
            frame.extend(struct.pack("!H", length))
        else:
            frame.append(0x80 | 127 if mask else 127)
            frame.extend(struct.pack("!Q", length))

        if mask:
            mask_key = os.urandom(4)
            frame.extend(mask_key)
            masked_payload = bytes(
                b ^ mask_key[i % 4] for i, b in enumerate(payload)
            )
            frame.extend(masked_payload)
        else:
            frame.extend(payload)

        return bytes(frame)

    @staticmethod
    def parse_frame(data: bytes) -> Optional[Tuple[int, bytes, int]]:
        """
        解析WebSocket数据帧

        Args:
            data: 接收到的原始数据

        Returns:
            元组 (opcode, payload, consumed_bytes)，解析失败返回None
        """
        if len(data) < 2:
            return None

        first_byte = data[0]
        second_byte = data[1]

        opcode = first_byte & 0x0F
        masked = bool(second_byte & 0x80)
        payload_length = second_byte & 0x7F

        offset = 2

        if payload_length == 126:
            if len(data) < offset + 2:
                return None
            payload_length = struct.unpack("!H", data[offset:offset + 2])[0]
            offset += 2
        elif payload_length == 127:
            if len(data) < offset + 8:
                return None
            payload_length = struct.unpack("!Q", data[offset:offset + 8])[0]
            offset += 8

        mask_key = None
        if masked:
            if len(data) < offset + 4:
                return None
            mask_key = data[offset:offset + 4]
            offset += 4

        total_length = offset + payload_length
        if len(data) < total_length:
            return None

        payload = data[offset:total_length]
        if masked and mask_key:
            payload = bytes(
                b ^ mask_key[i % 4] for i, b in enumerate(payload)
            )

        return (opcode, payload, total_length)


# ============================================================
# 内置WebSocket客户端（回退实现）
# ============================================================

class NativeWebSocketClient:
    """
    基于标准库socket+ssl的WebSocket客户端

    作为websockets库不可用时的回退方案。
    仅支持基本的文本消息收发。
    """

    def __init__(self):
        """初始化WebSocket客户端"""
        self._socket: Optional[socket.socket] = None
        self._buffer = b""
        self._closed = True

    async def connect(
        self, url: str, timeout: float = 30.0
    ) -> None:
        """
        连接到WebSocket服务器

        Args:
            url: WebSocket URL (ws:// 或 wss://)
            timeout: 连接超时时间（秒）
        """
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        # 创建TCP连接
        loop = asyncio.get_event_loop()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(timeout)

        await loop.sock_connect(self._socket, (host, port))

        # SSL包装
        if parsed.scheme == "wss":
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self._socket = context.wrap_socket(
                self._socket, server_hostname=host
            )

        # 发送WebSocket握手
        key = b64encode(os.urandom(16)).decode("ascii")
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        await loop.sock_sendall(self._socket, handshake.encode("utf-8"))

        # 读取握手响应
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = await loop.sock_recv(self._socket, 4096)
            if not chunk:
                raise ConnectionError("WebSocket握手失败：连接已关闭")
            response += chunk

        response_text = response.decode("utf-8", errors="replace")
        if "101" not in response_text.split("\r\n")[0]:
            raise ConnectionError(
                f"WebSocket握手失败：{response_text.split(chr(13))[0]}"
            )

        # 将剩余数据放入缓冲区
        header_end = response.index(b"\r\n\r\n") + 4
        self._buffer = response[header_end:]
        self._closed = False

    async def send(self, message: str) -> None:
        """
        发送文本消息

        Args:
            message: 要发送的文本消息
        """
        if self._socket is None or self._closed:
            raise ConnectionError("WebSocket未连接")

        frame = WebSocketFrame.build_frame(
            WS_OPCODE_TEXT, message.encode("utf-8"), mask=True
        )
        loop = asyncio.get_event_loop()
        await loop.sock_sendall(self._socket, frame)

    async def recv(self) -> Optional[str]:
        """
        接收文本消息

        Returns:
            接收到的文本消息，连接关闭返回None
        """
        if self._socket is None or self._closed:
            return None

        loop = asyncio.get_event_loop()

        while True:
            # 尝试从缓冲区解析帧
            result = WebSocketFrame.parse_frame(self._buffer)
            if result:
                opcode, payload, consumed = result
                self._buffer = self._buffer[consumed:]

                if opcode == WS_OPCODE_TEXT:
                    return payload.decode("utf-8", errors="replace")
                elif opcode == WS_OPCODE_CLOSE:
                    self._closed = True
                    return None
                elif opcode == WS_OPCODE_PING:
                    # 自动回复PONG
                    pong = WebSocketFrame.build_frame(
                        WS_OPCODE_PONG, payload, mask=True
                    )
                    await loop.sock_sendall(self._socket, pong)
                elif opcode == WS_OPCODE_BINARY:
                    return payload.decode("utf-8", errors="replace")
                continue

            # 需要读取更多数据
            try:
                chunk = await loop.sock_recv(self._socket, 4096)
                if not chunk:
                    self._closed = True
                    return None
                self._buffer += chunk
            except (socket.timeout, OSError):
                return None

    async def close(self) -> None:
        """关闭WebSocket连接"""
        if self._socket and not self._closed:
            try:
                frame = WebSocketFrame.build_frame(
                    WS_OPCODE_CLOSE, b"", mask=True
                )
                loop = asyncio.get_event_loop()
                await loop.sock_sendall(self._socket, frame)
            except (socket.error, OSError):
                pass
            try:
                self._socket.close()
            except (socket.error, OSError):
                pass
            self._closed = True

    @property
    def closed(self) -> bool:
        """连接是否已关闭"""
        return self._closed


# ============================================================
# CDP协议客户端
# ============================================================

class CDPClient:
    """
    Chrome DevTools Protocol客户端

    通过WebSocket连接到Chrome的远程调试端口，发送CDP命令
    并接收事件通知。支持自动重连和超时处理。

    Attributes:
        host: 调试服务器主机地址
        port: 调试服务器端口
        connected: 是否已连接
        ws_url: WebSocket连接URL

    Example:
        >>> client = CDPClient(port=9222)
        >>> await client.connect()
        >>> result = await client.send("Page.navigate", {"url": "https://example.com"})
        >>> await client.close()
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9222,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        初始化CDP客户端

        Args:
            host: 调试服务器主机地址
            port: 调试服务器端口
            timeout: 默认超时时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._ws: Optional[Any] = None
        self._message_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False
        self._ws_url: Optional[str] = None
        self._session_id: Optional[str] = None
        self._use_websockets_lib = False

    @property
    def connected(self) -> bool:
        """是否已连接到CDP服务器"""
        return self._connected

    @property
    def ws_url(self) -> Optional[str]:
        """WebSocket连接URL"""
        return self._ws_url

    def _next_id(self) -> int:
        """
        获取下一个消息ID

        Returns:
            递增的消息ID
        """
        self._message_id += 1
        return self._message_id

    async def _get_ws_endpoint(self) -> str:
        """
        通过HTTP获取CDP的WebSocket端点

        Returns:
            WebSocket URL

        Raises:
            ConnectionError: 无法连接到调试服务器
        """
        # 使用标准库发送HTTP请求获取调试信息
        import http.client

        for attempt in range(self.max_retries):
            try:
                conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
                conn.request("GET", "/json/version")
                response = conn.getresponse()
                data = json.loads(response.read().decode("utf-8"))
                conn.close()

                ws_url = data.get("webSocketDebuggerUrl")
                if ws_url:
                    return ws_url

                # 回退：尝试获取第一个page target
                conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
                conn.request("GET", "/json")
                response = conn.getresponse()
                targets = json.loads(response.read().decode("utf-8"))
                conn.close()

                for target in targets:
                    if target.get("type") == "page":
                        ws_url = target.get("webSocketDebuggerUrl")
                        if ws_url:
                            return ws_url

                raise ConnectionError("未找到可用的页面目标")

            except (ConnectionError, OSError, json.JSONDecodeError) as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise ConnectionError(
                        f"无法连接到调试服务器 {self.host}:{self.port} - {e}"
                    )

        raise ConnectionError("无法获取WebSocket端点")

    async def connect(self) -> None:
        """
        连接到CDP服务器

        首先通过HTTP获取WebSocket端点URL，然后建立WebSocket连接。
        优先使用websockets库，不可用时回退到内置实现。

        Raises:
            ConnectionError: 连接失败
        """
        # 获取WebSocket端点
        self._ws_url = await self._get_ws_endpoint()
        logger.info(f"连接到CDP: {self._ws_url}")

        # 尝试使用websockets库
        try:
            import websockets  # type: ignore

            self._ws = await websockets.connect(
                self._ws_url,
                max_size=10 * 1024 * 1024,  # 10MB
                ping_interval=20,
                ping_timeout=10,
            )
            self._use_websockets_lib = True
            logger.info("使用websockets库连接")
        except ImportError:
            # 回退到内置实现
            self._ws = NativeWebSocketClient()
            await self._ws.connect(self._ws_url, timeout=self.timeout)
            self._use_websockets_lib = False
            logger.info("使用内置WebSocket客户端连接")

        self._connected = True

        # 启动消息接收循环
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info("CDP客户端已连接")

    async def _receive_loop(self) -> None:
        """消息接收循环，持续监听CDP消息"""
        while self._connected:
            try:
                if self._use_websockets_lib:
                    message = await self._ws.recv()  # type: ignore
                else:
                    message = await self._ws.recv()  # type: ignore

                if message is None:
                    logger.warning("WebSocket连接已关闭")
                    self._connected = False
                    break

                await self._handle_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._connected:
                    logger.error(f"接收消息时出错: {e}")
                    await asyncio.sleep(0.1)

    async def _handle_message(self, message: str) -> None:
        """
        处理接收到的CDP消息

        Args:
            message: 原始消息字符串
        """
        data = safe_json_loads(message)
        if data is None:
            logger.warning(f"无法解析消息: {message[:200]}")
            return

        # 检查是否为响应消息
        if "id" in data:
            msg_id = data.get("id")
            if msg_id in self._pending:
                future = self._pending.pop(msg_id)
                if not future.done():
                    if "error" in data:
                        future.set_exception(
                            CDPError(
                                data["error"].get("code", -1),
                                data["error"].get("message", "Unknown error"),
                            )
                        )
                    else:
                        future.set_result(data.get("result", {}))
            return

        # 检查是否为事件消息
        if "method" in data:
            method = data["method"]
            params = data.get("params", {})

            # 分发给事件处理器
            handlers = self._event_handlers.get(method, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(params)
                    else:
                        handler(params)
                except Exception as e:
                    logger.error(f"事件处理器出错 ({method}): {e}")

            # 通配符处理器
            wildcard_handlers = self._event_handlers.get("*", [])
            for handler in wildcard_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(method, params)
                    else:
                        handler(method, params)
                except Exception as e:
                    logger.error(f"通配符事件处理器出错: {e}")

    async def send(
        self, method: str, params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        发送CDP命令

        Args:
            method: CDP方法名（如 "Page.navigate"）
            params: CDP方法参数
            timeout: 超时时间（秒），None使用默认值

        Returns:
            CDP命令的响应结果

        Raises:
            CDPError: CDP命令执行出错
            asyncio.TimeoutError: 命令超时
            ConnectionError: 未连接
        """
        if not self._connected or self._ws is None:
            raise ConnectionError("未连接到CDP服务器")

        msg_id = self._next_id()
        message = {"id": msg_id, "method": method}
        if params:
            message["params"] = params

        # 创建Future等待响应
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[msg_id] = future

        # 发送消息
        message_str = json.dumps(message, ensure_ascii=False)
        try:
            if self._use_websockets_lib:
                await self._ws.send(message_str)  # type: ignore
            else:
                await self._ws.send(message_str)  # type: ignore
        except Exception as e:
            self._pending.pop(msg_id, None)
            raise ConnectionError(f"发送消息失败: {e}")

        # 等待响应
        try:
            result = await asyncio.wait_for(
                future, timeout=timeout or self.timeout
            )
            return result
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise asyncio.TimeoutError(
                f"CDP命令超时 ({method}, {timeout or self.timeout}s)"
            )

    def on(
        self, event: str, handler: Callable
    ) -> Callable:
        """
        注册CDP事件处理器

        Args:
            event: CDP事件名（如 "Page.loadEventFired"），"*" 匹配所有事件
            handler: 事件处理函数，接收params字典参数

        Returns:
            取消注册函数
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

        def unregister():
            if event in self._event_handlers:
                try:
                    self._event_handlers[event].remove(handler)
                except ValueError:
                    pass

        return unregister

    async def reconnect(self) -> None:
        """
        重新连接到CDP服务器

        关闭现有连接并重新建立连接。
        """
        await self.close()
        await self.connect()

    async def close(self) -> None:
        """关闭CDP连接"""
        self._connected = False

        # 取消接收任务
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        # 关闭WebSocket
        if self._ws:
            try:
                if self._use_websockets_lib:
                    await self._ws.close()  # type: ignore
                else:
                    await self._ws.close()  # type: ignore
            except Exception:
                pass
            self._ws = None

        # 取消所有等待中的请求
        for msg_id, future in self._pending.items():
            if not future.done():
                future.set_exception(ConnectionError("连接已关闭"))
        self._pending.clear()

        logger.info("CDP客户端已关闭")

    def __repr__(self) -> str:
        return f"CDPClient(host={self.host!r}, port={self.port}, connected={self._connected})"

    async def __aenter__(self) -> "CDPClient":
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.close()


class CDPError(Exception):
    """
    CDP协议错误

    当CDP命令返回错误响应时抛出。

    Attributes:
        code: CDP错误码
        message: 错误描述
    """

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"CDP Error [{code}]: {message}")

    def __repr__(self) -> str:
        return f"CDPError(code={self.code}, message={self.message!r})"
