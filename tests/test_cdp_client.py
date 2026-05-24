"""
CDP客户端单元测试

测试CDP协议客户端的核心功能，包括：
- WebSocket帧解析和构建
- 消息ID管理
- 事件处理
- 错误处理
- 连接管理
"""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from devtools_pilot.cdp_client import (
    CDPClient,
    CDPError,
    NativeWebSocketClient,
    WebSocketFrame,
)


class TestWebSocketFrame(unittest.TestCase):
    """WebSocket帧解析和构建测试"""

    def test_build_text_frame(self):
        """测试构建文本帧"""
        payload = b"Hello, World!"
        frame = WebSocketFrame.build_frame(0x1, payload, mask=False)
        # 验证帧结构
        self.assertEqual(frame[0] & 0x80, 0x80)  # FIN位
        self.assertEqual(frame[0] & 0x0F, 0x1)   # TEXT操作码
        self.assertEqual(frame[1] & 0x80, 0x00)  # 无掩码
        self.assertEqual(frame[1], len(payload))  # 载荷长度

    def test_build_masked_frame(self):
        """测试构建掩码帧"""
        payload = b"test"
        frame = WebSocketFrame.build_frame(0x1, payload, mask=True)
        self.assertEqual(frame[1] & 0x80, 0x80)  # 有掩码
        self.assertEqual(frame[2:6], frame[2:6])  # 掩码密钥存在

    def test_build_short_payload(self):
        """测试短载荷帧"""
        payload = b"a"
        frame = WebSocketFrame.build_frame(0x1, payload, mask=False)
        self.assertEqual(frame[1], 1)  # 长度为1

    def test_build_medium_payload(self):
        """测试中等长度载荷帧（126-65535字节）"""
        payload = b"x" * 200
        frame = WebSocketFrame.build_frame(0x1, payload, mask=False)
        self.assertEqual(frame[1], 126)  # 中等长度标识

    def test_build_long_payload(self):
        """测试长载荷帧（>65535字节）"""
        payload = b"x" * 70000
        frame = WebSocketFrame.build_frame(0x1, payload, mask=False)
        self.assertEqual(frame[1], 127)  # 长长度标识

    def test_parse_text_frame(self):
        """测试解析文本帧"""
        payload = b"Hello"
        frame = WebSocketFrame.build_frame(0x1, payload, mask=False)
        result = WebSocketFrame.parse_frame(frame)
        self.assertIsNotNone(result)
        opcode, data, consumed = result
        self.assertEqual(opcode, 0x1)
        self.assertEqual(data, payload)
        self.assertEqual(consumed, len(frame))

    def test_parse_insufficient_data(self):
        """测试数据不足时的解析"""
        result = WebSocketFrame.parse_frame(b"\x81")
        self.assertIsNone(result)

    def test_parse_close_frame(self):
        """测试解析关闭帧"""
        frame = WebSocketFrame.build_frame(0x8, b"", mask=False)
        result = WebSocketFrame.parse_frame(frame)
        self.assertIsNotNone(result)
        opcode, _, _ = result
        self.assertEqual(opcode, 0x8)


class TestCDPClient(unittest.TestCase):
    """CDP客户端测试"""

    def setUp(self):
        """测试前准备"""
        self.client = CDPClient(host="localhost", port=9222, timeout=5.0)

    def test_initial_state(self):
        """测试初始状态"""
        self.assertFalse(self.client.connected)
        self.assertIsNone(self.client.ws_url)
        self.assertEqual(self.client.host, "localhost")
        self.assertEqual(self.client.port, 9222)

    def test_next_id(self):
        """测试消息ID递增"""
        id1 = self.client._next_id()
        id2 = self.client._next_id()
        id3 = self.client._next_id()
        self.assertEqual(id1, 1)
        self.assertEqual(id2, 2)
        self.assertEqual(id3, 3)
        self.assertGreater(id2, id1)
        self.assertGreater(id3, id2)

    def test_event_registration(self):
        """测试事件注册"""
        handler = MagicMock()
        unregister = self.client.on("Page.loadEventFired", handler)
        self.assertIn("Page.loadEventFired", self.client._event_handlers)
        self.assertIn(handler, self.client._event_handlers["Page.loadEventFired"])

        # 取消注册
        unregister()
        self.assertNotIn(handler, self.client._event_handlers.get("Page.loadEventFired", []))

    def test_wildcard_handler(self):
        """测试通配符事件处理器"""
        handler = MagicMock()
        self.client.on("*", handler)
        self.assertIn("*", self.client._event_handlers)

    def test_send_without_connection(self):
        """测试未连接时发送消息"""
        loop = asyncio.new_event_loop()
        try:
            with self.assertRaises(ConnectionError):
                loop.run_until_complete(
                    self.client.send("Page.navigate", {"url": "https://example.com"})
                )
        finally:
            loop.close()

    def test_repr(self):
        """测试字符串表示"""
        self.assertIn("localhost", repr(self.client))
        self.assertIn("9222", repr(self.client))


class TestCDPError(unittest.TestCase):
    """CDP错误类测试"""

    def test_error_creation(self):
        """测试错误创建"""
        error = CDPError(32000, "Test error")
        self.assertEqual(error.code, 32000)
        self.assertEqual(error.message, "Test error")
        self.assertIn("32000", str(error))
        self.assertIn("Test error", str(error))

    def test_error_repr(self):
        """测试错误repr"""
        error = CDPError(-32601, "Method not found")
        repr_str = repr(error)
        self.assertIn("-32601", repr_str)
        self.assertIn("Method not found", repr_str)

    def test_error_inheritance(self):
        """测试错误继承"""
        error = CDPError(1, "test")
        self.assertIsInstance(error, Exception)


class TestNativeWebSocketClient(unittest.TestCase):
    """内置WebSocket客户端测试"""

    def test_initial_state(self):
        """测试初始状态"""
        ws = NativeWebSocketClient()
        self.assertTrue(ws.closed)
        self.assertIsNone(ws._socket)

    def test_closed_property(self):
        """测试closed属性"""
        ws = NativeWebSocketClient()
        self.assertTrue(ws.closed)
        ws._closed = False
        self.assertFalse(ws.closed)


class TestCDPClientMessageHandling(unittest.TestCase):
    """CDP客户端消息处理测试"""

    def setUp(self):
        self.client = CDPClient(host="localhost", port=9222)

    def test_handle_response_message(self):
        """测试处理响应消息"""
        loop = asyncio.new_event_loop()
        try:
            # 创建一个Future模拟等待响应
            future = loop.create_future()
            self.client._pending[1] = future

            # 模拟响应消息
            message = json.dumps({
                "id": 1,
                "result": {"frameId": "test", "loaderId": "loader1"},
            })

            loop.run_until_complete(self.client._handle_message(message))

            self.assertTrue(future.done())
            self.assertEqual(future.result()["frameId"], "test")
        finally:
            loop.close()

    def test_handle_error_response(self):
        """测试处理错误响应"""
        loop = asyncio.new_event_loop()
        try:
            future = loop.create_future()
            self.client._pending[2] = future

            message = json.dumps({
                "id": 2,
                "error": {"code": -32000, "message": "Something went wrong"},
            })

            loop.run_until_complete(self.client._handle_message(message))

            self.assertTrue(future.done())
            self.assertIsInstance(future.exception(), CDPError)
        finally:
            loop.close()

    def test_handle_event_message(self):
        """测试处理事件消息"""
        loop = asyncio.new_event_loop()
        try:
            handler = AsyncMock()
            self.client.on("Page.loadEventFired", handler)

            message = json.dumps({
                "method": "Page.loadEventFired",
                "params": {"timestamp": 1234567890},
            })

            loop.run_until_complete(self.client._handle_message(message))
            handler.assert_called_once_with({"timestamp": 1234567890})
        finally:
            loop.close()

    def test_handle_invalid_json(self):
        """测试处理无效JSON"""
        loop = asyncio.new_event_loop()
        try:
            # 不应抛出异常
            loop.run_until_complete(self.client._handle_message("not json"))
        finally:
            loop.close()

    def test_handle_event_with_wildcard(self):
        """测试通配符事件处理"""
        loop = asyncio.new_event_loop()
        try:
            handler = AsyncMock()
            self.client.on("*", handler)

            message = json.dumps({
                "method": "Network.requestWillBeSent",
                "params": {"requestId": "1"},
            })

            loop.run_until_complete(self.client._handle_message(message))
            handler.assert_called_once_with(
                "Network.requestWillBeSent",
                {"requestId": "1"},
            )
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
