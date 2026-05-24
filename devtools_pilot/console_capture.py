"""
控制台日志捕获模块

通过CDP Runtime/Log域捕获浏览器控制台输出：
- 捕获console.log/warn/error/info/debug
- 日志级别过滤
- 实时日志流
- 日志统计
"""

import asyncio
import logging
import time
from collections import defaultdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .cdp_client import CDPClient
from .utils import format_datetime, timestamp_to_datetime, truncate

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """控制台日志级别"""
    LOG = "log"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"

    @classmethod
    def from_string(cls, value: str) -> "LogLevel":
        """从字符串创建日志级别"""
        value = value.lower()
        for level in cls:
            if level.value == value:
                return level
        return cls.LOG


class ConsoleMessage:
    """
    控制台消息记录

    Attributes:
        level: 日志级别
        text: 消息文本
        url: 来源URL
        line: 行号
        column: 列号
        timestamp: 时间戳
        source: 消息来源
        args: 原始参数列表
    """

    def __init__(
        self,
        level: LogLevel = LogLevel.LOG,
        text: str = "",
        url: str = "",
        line: int = 0,
        column: int = 0,
        timestamp: float = 0.0,
        source: str = "",
        args: Optional[List[Dict[str, Any]]] = None,
    ):
        self.level = level
        self.text = text
        self.url = url
        self.line = line
        self.column = column
        self.timestamp = timestamp or time.time()
        self.source = source
        self.args = args or []

    @property
    def time_str(self) -> str:
        """格式化的时间字符串"""
        return format_datetime(timestamp_to_datetime(self.timestamp))

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "level": self.level.value,
            "text": self.text,
            "url": self.url,
            "line": self.line,
            "column": self.column,
            "timestamp": self.timestamp,
            "time": self.time_str,
            "source": self.source,
        }

    def __repr__(self) -> str:
        return (
            f"ConsoleMessage(level={self.level.value}, "
            f"text={truncate(self.text, 50)!r})"
        )


class ConsoleCapture:
    """
    控制台日志捕获器

    通过CDP Runtime和Log域捕获浏览器控制台输出，
    支持日志级别过滤和实时日志流。

    Attributes:
        client: CDP客户端实例
        messages: 所有已捕获的消息
        is_capturing: 是否正在捕获

    Example:
        >>> capture = ConsoleCapture(client)
        >>> await capture.enable()
        >>> # ... 执行页面操作 ...
        >>> errors = capture.get_messages(LogLevel.ERROR)
        >>> await capture.disable()
    """

    def __init__(
        self,
        client: CDPClient,
        min_level: Optional[LogLevel] = None,
    ):
        """
        初始化控制台捕获器

        Args:
            client: CDP客户端实例
            min_level: 最低捕获级别，None则捕获所有
        """
        self.client = client
        self.min_level = min_level
        self.messages: List[ConsoleMessage] = []
        self._is_capturing = False
        self._unregister_handlers = []
        self._stream_callbacks: List[Callable] = []
        self._level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.LOG: 1,
            LogLevel.INFO: 2,
            LogLevel.WARNING: 3,
            LogLevel.ERROR: 4,
        }

    @property
    def is_capturing(self) -> bool:
        """是否正在捕获"""
        return self._is_capturing

    def _should_capture(self, level: LogLevel) -> bool:
        """
        判断是否应该捕获指定级别的日志

        Args:
            level: 日志级别

        Returns:
            是否应该捕获
        """
        if self.min_level is None:
            return True
        return self._level_order.get(level, 0) >= self._level_order.get(self.min_level, 0)

    async def enable(self) -> None:
        """启用控制台捕获"""
        # 注册Runtime.consoleAPICalled事件
        async def on_console_api_called(params: Dict[str, Any]) -> None:
            await self._handle_console_event(params)

        # 注册Runtime.exceptionThrown事件
        async def on_exception_thrown(params: Dict[str, Any]) -> None:
            await self._handle_exception_event(params)

        # 注册Log.entryAdded事件
        async def on_log_entry_added(params: Dict[str, Any]) -> None:
            await self._handle_log_event(params)

        self._unregister_handlers.append(
            self.client.on("Runtime.consoleAPICalled", on_console_api_called)
        )
        self._unregister_handlers.append(
            self.client.on("Runtime.exceptionThrown", on_exception_thrown)
        )
        self._unregister_handlers.append(
            self.client.on("Log.entryAdded", on_log_entry_added)
        )

        # 启用Runtime和Log域
        await self.client.send("Runtime.enable")
        try:
            await self.client.send("Log.enable")
        except Exception:
            # Log域可能不可用
            pass

        self._is_capturing = True
        logger.info("控制台捕获已启用")

    async def disable(self) -> None:
        """禁用控制台捕获"""
        self._is_capturing = False

        try:
            await self.client.send("Runtime.disable")
        except Exception:
            pass

        try:
            await self.client.send("Log.disable")
        except Exception:
            pass

        for unregister in self._unregister_handlers:
            unregister()
        self._unregister_handlers.clear()
        logger.info("控制台捕获已禁用")

    async def _handle_console_event(self, params: Dict[str, Any]) -> None:
        """
        处理console API调用事件

        Args:
            params: CDP事件参数
        """
        if not self._is_capturing:
            return

        type_str = params.get("type", "log")
        level = LogLevel.from_string(type_str)

        if not self._should_capture(level):
            return

        # 提取消息文本
        args = params.get("args", [])
        text_parts = []
        for arg in args:
            if isinstance(arg, dict):
                arg_type = arg.get("type", "")
                value = arg.get("value", "")
                if arg_type == "string":
                    text_parts.append(str(value))
                elif arg_type == "undefined":
                    text_parts.append("undefined")
                elif arg_type == "object":
                    desc = arg.get("description", arg.get("className", "[Object]"))
                    text_parts.append(str(desc))
                else:
                    text_parts.append(str(value) if value else str(arg))
            else:
                text_parts.append(str(arg))

        text = " ".join(text_parts)

        msg = ConsoleMessage(
            level=level,
            text=text,
            url=params.get("url", ""),
            line=params.get("lineNumber", 0),
            column=params.get("columnNumber", 0),
            timestamp=params.get("timestamp", time.time() * 1000) / 1000.0,
            source="console-api",
            args=args,
        )

        self.messages.append(msg)
        await self._notify_stream(msg)

    async def _handle_exception_event(self, params: Dict[str, Any]) -> None:
        """
        处理异常事件

        Args:
            params: CDP事件参数
        """
        if not self._is_capturing:
            return

        if not self._should_capture(LogLevel.ERROR):
            return

        exception = params.get("exceptionDetails", {})
        text = exception.get("text", "Unknown exception")

        # 尝试获取更详细的异常信息
        exception_obj = exception.get("exception", {})
        if exception_obj:
            desc = exception_obj.get("description", "")
            if desc:
                text = desc

        msg = ConsoleMessage(
            level=LogLevel.ERROR,
            text=text,
            url=exception.get("url", ""),
            line=exception.get("lineNumber", 0),
            column=exception.get("columnNumber", 0),
            timestamp=time.time(),
            source="exception",
        )

        self.messages.append(msg)
        await self._notify_stream(msg)

    async def _handle_log_event(self, params: Dict[str, Any]) -> None:
        """
        处理Log.entryAdded事件

        Args:
            params: CDP事件参数
        """
        if not self._is_capturing:
            return

        entry = params.get("entry", {})
        level_str = entry.get("level", "log")
        level = LogLevel.from_string(level_str)

        if not self._should_capture(level):
            return

        text = entry.get("text", "")
        url = entry.get("url", "")
        line = entry.get("lineNumber", 0)

        msg = ConsoleMessage(
            level=level,
            text=text,
            url=url,
            line=line,
            timestamp=entry.get("timestamp", time.time() * 1000) / 1000.0,
            source="browser-log",
        )

        self.messages.append(msg)
        await self._notify_stream(msg)

    async def _notify_stream(self, msg: ConsoleMessage) -> None:
        """通知流回调"""
        for callback in self._stream_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(msg)
                else:
                    callback(msg)
            except Exception as e:
                logger.error(f"流回调出错: {e}")

    def on_message(self, callback: Callable) -> Callable:
        """
        注册实时消息回调

        Args:
            callback: 回调函数，接收ConsoleMessage参数

        Returns:
            取消注册函数
        """
        self._stream_callbacks.append(callback)

        def unregister():
            if callback in self._stream_callbacks:
                self._stream_callbacks.remove(callback)

        return unregister

    def get_messages(
        self,
        level: Optional[LogLevel] = None,
        url_filter: Optional[str] = None,
        text_filter: Optional[str] = None,
        limit: int = 0,
    ) -> List[ConsoleMessage]:
        """
        获取过滤后的消息列表

        Args:
            level: 日志级别过滤
            url_filter: URL过滤
            text_filter: 文本内容过滤
            limit: 最大返回数量，0表示不限制

        Returns:
            过滤后的消息列表
        """
        result = self.messages

        if level:
            result = [m for m in result if m.level == level]
        if url_filter:
            result = [m for m in result if url_filter in m.url]
        if text_filter:
            result = [m for m in result if text_filter in m.text]
        if limit > 0:
            result = result[-limit:]

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取控制台消息统计

        Returns:
            统计信息字典
        """
        total = len(self.messages)
        by_level: Dict[str, int] = defaultdict(int)
        by_source: Dict[str, int] = defaultdict(int)
        by_url: Dict[str, int] = defaultdict(int)

        for msg in self.messages:
            by_level[msg.level.value] += 1
            by_source[msg.source] += 1
            if msg.url:
                by_url[msg.url] += 1

        return {
            "totalMessages": total,
            "byLevel": dict(by_level),
            "bySource": dict(by_source),
            "topUrls": dict(
                sorted(by_url.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "errorCount": by_level.get("error", 0),
            "warningCount": by_level.get("warning", 0),
        }

    def clear(self) -> None:
        """清除所有已捕获的消息"""
        self.messages.clear()

    def __repr__(self) -> str:
        return (
            f"ConsoleCapture(messages={len(self.messages)}, "
            f"capturing={self._is_capturing})"
        )
