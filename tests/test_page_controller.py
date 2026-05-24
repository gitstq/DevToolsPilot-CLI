"""
页面控制器单元测试

测试页面控制器的核心功能，包括：
- 页面导航
- JavaScript执行
- DOM操作
- Cookie管理
- 事件监听
"""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from devtools_pilot.cdp_client import CDPClient, CDPError
from devtools_pilot.page_controller import PageController


class TestPageController(unittest.TestCase):
    """页面控制器测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_client = MagicMock(spec=CDPClient)
        self.mock_client.send = AsyncMock()
        self.mock_client.on = MagicMock(return_value=MagicMock())
        self.controller = PageController(self.mock_client, navigation_timeout=10.0)

    def test_initial_state(self):
        """测试初始状态"""
        self.assertEqual(self.controller.current_url, "")
        self.assertEqual(self.controller.title, "")
        self.assertEqual(self.controller.navigation_timeout, 10.0)

    def test_enable(self):
        """测试启用页面控制"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {"frameTree": {"frame": {"url": ""}}}
            loop.run_until_complete(self.controller.enable())
            self.mock_client.send.assert_any_call("Page.enable")
        finally:
            loop.close()

    def test_goto(self):
        """测试页面导航"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {"frameTree": {"frame": {"url": ""}}}
            loop.run_until_complete(self.controller.enable())

            self.mock_client.send.return_value = {
                "frameId": "test-frame",
            }

            # 模拟导航完成
            async def mock_send(method, params=None, timeout=None):
                if method == "Page.navigate":
                    return {"frameId": "test-frame"}
                return {}

            self.mock_client.send = AsyncMock(side_effect=mock_send)

            # 手动触发事件
            self.controller._load_event_fired.set()

            result = loop.run_until_complete(
                self.controller.goto("https://example.com", wait_until="none")
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["url"], "https://example.com")
            self.assertEqual(self.controller.current_url, "https://example.com")
        finally:
            loop.close()

    def test_evaluate_success(self):
        """测试JavaScript执行成功"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "string", "value": "Hello"},
            }

            result = loop.run_until_complete(
                self.controller.evaluate("document.title")
            )

            self.assertEqual(result, "Hello")
            call_args = self.mock_client.send.call_args
            self.assertEqual(call_args[0][0], "Runtime.evaluate")
        finally:
            loop.close()

    def test_evaluate_undefined(self):
        """测试JavaScript返回undefined"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "undefined"},
            }

            result = loop.run_until_complete(
                self.controller.evaluate("void 0")
            )

            self.assertIsNone(result)
        finally:
            loop.close()

    def test_evaluate_exception(self):
        """测试JavaScript执行异常"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "exceptionDetails": {
                    "exception": {
                        "description": "TypeError: Cannot read property of null",
                    }
                }
            }

            with self.assertRaises(CDPError):
                loop.run_until_complete(
                    self.controller.evaluate("null.foo")
                )
        finally:
            loop.close()

    def test_get_title(self):
        """测试获取页面标题"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "string", "value": "Test Page"},
            }

            title = loop.run_until_complete(self.controller.get_title())
            self.assertEqual(title, "Test Page")
            self.assertEqual(self.controller.title, "Test Page")
        finally:
            loop.close()

    def test_get_url(self):
        """测试获取页面URL"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "string", "value": "https://example.com"},
            }

            url = loop.run_until_complete(self.controller.get_url())
            self.assertEqual(url, "https://example.com")
        finally:
            loop.close()

    def test_get_cookies(self):
        """测试获取Cookie"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "cookies": [
                    {"name": "session", "value": "abc123", "domain": ".example.com"},
                ],
            }

            cookies = loop.run_until_complete(self.controller.get_cookies())
            self.assertEqual(len(cookies), 1)
            self.assertEqual(cookies[0]["name"], "session")
        finally:
            loop.close()

    def test_set_cookie(self):
        """测试设置Cookie"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {"success": True}

            result = loop.run_until_complete(
                self.controller.set_cookie("test", "value", domain=".example.com")
            )

            self.assertTrue(result)
            call_args = self.mock_client.send.call_args
            self.assertEqual(call_args[0][0], "Network.setCookie")
            params = call_args[0][1]
            self.assertEqual(params["name"], "test")
            self.assertEqual(params["value"], "value")
        finally:
            loop.close()

    def test_clear_cookies(self):
        """测试清除Cookie"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {}

            result = loop.run_until_complete(self.controller.clear_cookies())
            self.assertTrue(result)
            self.mock_client.send.assert_called_with("Network.clearBrowserCookies")
        finally:
            loop.close()

    def test_get_text_content(self):
        """测试获取元素文本"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "string", "value": "Hello World"},
            }

            text = loop.run_until_complete(
                self.controller.get_text_content("h1")
            )
            self.assertEqual(text, "Hello World")
        finally:
            loop.close()

    def test_get_inner_html(self):
        """测试获取元素HTML"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "string", "value": "<p>Hello</p>"},
            }

            html = loop.run_until_complete(
                self.controller.get_inner_html("div.content")
            )
            self.assertEqual(html, "<p>Hello</p>")
        finally:
            loop.close()

    def test_repr(self):
        """测试字符串表示"""
        self.controller.current_url = "https://example.com"
        self.controller.title = "Example"
        repr_str = repr(self.controller)
        self.assertIn("https://example.com", repr_str)
        self.assertIn("Example", repr_str)


class TestPageControllerDOM(unittest.TestCase):
    """页面控制器DOM操作测试"""

    def setUp(self):
        self.mock_client = MagicMock(spec=CDPClient)
        self.mock_client.send = AsyncMock()
        self.mock_client.on = MagicMock(return_value=MagicMock())
        self.controller = PageController(self.mock_client)

    def test_query_selector_found(self):
        """测试查找存在的元素"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {
                    "type": "object",
                    "subtype": "node",
                    "className": "HTMLDivElement",
                    "description": "div.test",
                },
            }

            result = loop.run_until_complete(
                self.controller.query_selector("div.test")
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["type"], "object")
        finally:
            loop.close()

    def test_query_selector_not_found(self):
        """测试查找不存在的元素"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "undefined"},
            }

            result = loop.run_until_complete(
                self.controller.query_selector("#nonexistent")
            )
            self.assertIsNone(result)
        finally:
            loop.close()

    def test_get_attribute(self):
        """测试获取元素属性"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "string", "value": "https://example.com"},
            }

            href = loop.run_until_complete(
                self.controller.get_attribute("a.link", "href")
            )
            self.assertEqual(href, "https://example.com")
        finally:
            loop.close()

    def test_set_property(self):
        """测试设置CSS属性"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "undefined"},
            }

            result = loop.run_until_complete(
                self.controller.set_property("div", "display", "none")
            )
            self.assertTrue(result)
        finally:
            loop.close()

    def test_click_element(self):
        """测试点击元素"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "undefined"},
            }

            result = loop.run_until_complete(
                self.controller.click_element("button.submit")
            )
            self.assertTrue(result)
        finally:
            loop.close()

    def test_wait_for_selector_timeout(self):
        """测试等待元素超时"""
        loop = asyncio.new_event_loop()
        try:
            self.mock_client.send.return_value = {
                "result": {"type": "boolean", "value": False},
            }

            result = loop.run_until_complete(
                self.controller.wait_for_selector("#slow-element", timeout=0.5, interval=0.1)
            )
            self.assertFalse(result)
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
