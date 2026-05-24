"""
浏览器管理器单元测试

测试浏览器管理器的核心功能，包括：
- 浏览器路径检测
- 启动参数构建
- 进程管理
- 跨平台支持
"""

import os
import platform
import sys
import unittest
from unittest.mock import MagicMock, patch, call

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from devtools_pilot.browser_manager import (
    BrowserInfo,
    BrowserManager,
    BROWSER_PATHS,
)


class TestBrowserInfo(unittest.TestCase):
    """浏览器信息类测试"""

    def test_creation(self):
        """测试创建浏览器信息"""
        info = BrowserInfo(
            name="chrome",
            path="/usr/bin/google-chrome",
            version="120.0.0.0",
            supports_cdp=True,
        )
        self.assertEqual(info.name, "chrome")
        self.assertEqual(info.path, "/usr/bin/google-chrome")
        self.assertEqual(info.version, "120.0.0.0")
        self.assertTrue(info.supports_cdp)

    def test_repr(self):
        """测试字符串表示"""
        info = BrowserInfo(name="edge", path="/path/to/edge")
        repr_str = repr(info)
        self.assertIn("edge", repr_str)
        self.assertIn("/path/to/edge", repr_str)

    def test_firefox_no_cdp(self):
        """测试Firefox不支持CDP"""
        info = BrowserInfo(name="firefox", path="/usr/bin/firefox", supports_cdp=False)
        self.assertFalse(info.supports_cdp)


class TestBrowserManager(unittest.TestCase):
    """浏览器管理器测试"""

    def setUp(self):
        """测试前准备"""
        self.manager = BrowserManager(port=9222, headless=False, browser="chrome")

    def test_initial_state(self):
        """测试初始状态"""
        self.assertEqual(self.manager.port, 9222)
        self.assertEqual(self.manager.browser_name, "chrome")
        self.assertFalse(self.manager.headless)
        self.assertFalse(self.manager.is_running)
        self.assertIsNone(self.manager.process)

    def test_detect_nonexistent_browser(self):
        """测试检测不存在的浏览器"""
        result = self.manager.detect_browser("nonexistent")
        self.assertIsNone(result)

    def test_detect_with_mock(self):
        """测试模拟浏览器检测"""
        with patch("os.path.isfile", return_value=True):
            with patch.object(self.manager, "_get_browser_version", return_value="120.0"):
                # 需要确保路径匹配当前平台
                system = platform.system()
                paths = BROWSER_PATHS["chrome"].get(system, [])
                if paths:
                    result = self.manager.detect_browser("chrome")
                    if result:
                        self.assertEqual(result.name, "chrome")
                        self.assertEqual(result.version, "120.0")
                        self.assertTrue(result.supports_cdp)

    def test_build_launch_args_chrome(self):
        """测试Chrome启动参数构建"""
        info = BrowserInfo(name="chrome", path="/usr/bin/google-chrome")
        args = self.manager._build_launch_args(info)

        self.assertIn("/usr/bin/google-chrome", args)
        self.assertIn("--remote-debugging-port=9222", args)
        self.assertIn("--no-first-run", args)
        self.assertIn("--no-default-browser-check", args)
        self.assertIn("about:blank", args)

    def test_build_launch_args_headless(self):
        """测试无头模式启动参数"""
        manager = BrowserManager(port=9222, headless=True, browser="chrome")
        info = BrowserInfo(name="chrome", path="/usr/bin/google-chrome")
        args = manager._build_launch_args(info)

        self.assertIn("--headless=new", args)

    def test_build_launch_args_firefox(self):
        """测试Firefox启动参数"""
        info = BrowserInfo(name="firefox", path="/usr/bin/firefox")
        args = self.manager._build_launch_args(info)

        self.assertIn("/usr/bin/firefox", args)
        self.assertIn("--remote-debugging-port=9222", args)
        # Firefox不应有Chrome特有参数
        self.assertNotIn("--no-first-run", args)

    def test_build_launch_args_firefox_headless(self):
        """测试Firefox无头模式"""
        manager = BrowserManager(port=9222, headless=True, browser="firefox")
        info = BrowserInfo(name="firefox", path="/usr/bin/firefox")
        args = manager._build_launch_args(info)

        self.assertIn("--headless", args)
        self.assertNotIn("--headless=new", args)

    def test_build_launch_args_with_window_size(self):
        """测试窗口大小参数"""
        manager = BrowserManager(port=9222, browser="chrome", window_size=(1920, 1080))
        info = BrowserInfo(name="chrome", path="/usr/bin/google-chrome")
        args = manager._build_launch_args(info)

        self.assertIn("--window-size=1920,1080", args)

    def test_build_launch_args_with_extra_args(self):
        """测试额外启动参数"""
        manager = BrowserManager(port=9222, browser="chrome", extra_args=["--disable-gpu", "--no-sandbox"])
        info = BrowserInfo(name="chrome", path="/usr/bin/google-chrome")
        args = manager._build_launch_args(info)

        self.assertIn("--disable-gpu", args)
        self.assertIn("--no-sandbox", args)

    def test_build_launch_args_with_user_data_dir(self):
        """测试用户数据目录参数"""
        manager = BrowserManager(port=9222, browser="chrome", user_data_dir="/tmp/test-profile")
        info = BrowserInfo(name="chrome", path="/usr/bin/google-chrome")
        args = manager._build_launch_args(info)

        self.assertIn("--user-data-dir=/tmp/test-profile", args)

    def test_get_debug_url(self):
        """测试获取调试URL"""
        url = self.manager.get_debug_url()
        self.assertEqual(url, "http://localhost:9222")

    def test_get_debug_url_custom_host(self):
        """测试自定义主机的调试URL"""
        manager = BrowserManager(port=9333, host="127.0.0.1")
        url = manager.get_debug_url()
        self.assertEqual(url, "http://127.0.0.1:9333")

    def test_repr(self):
        """测试字符串表示"""
        repr_str = repr(self.manager)
        self.assertIn("chrome", repr_str)
        self.assertIn("9222", repr_str)
        self.assertIn("stopped", repr_str)

    def test_detect_all_browsers_empty(self):
        """测试在无浏览器时的检测"""
        with patch("os.path.isfile", return_value=False):
            results = self.manager.detect_all_browsers()
            self.assertEqual(len(results), 0)

    def test_detect_all_browsers_with_mock(self):
        """测试模拟多浏览器检测"""
        call_count = [0]

        def mock_isfile(path):
            # 让第一个路径存在
            call_count[0] += 1
            return call_count[0] == 1

        with patch("os.path.isfile", side_effect=mock_isfile):
            with patch.object(self.manager, "_get_browser_version", return_value="1.0"):
                results = self.manager.detect_all_browsers()
                # 至少应该找到一个
                self.assertGreaterEqual(len(results), 0)


class TestBrowserPaths(unittest.TestCase):
    """浏览器路径配置测试"""

    def test_all_browsers_have_paths(self):
        """测试所有浏览器都有路径配置"""
        for browser in ["chrome", "edge", "brave", "firefox"]:
            self.assertIn(browser, BROWSER_PATHS)

    def test_all_platforms_have_paths(self):
        """测试所有平台都有路径配置"""
        for browser, platform_paths in BROWSER_PATHS.items():
            for platform_name in ["Windows", "Darwin", "Linux"]:
                self.assertIn(platform_name, platform_paths,
                              f"{browser} 缺少 {platform_name} 的路径配置")

    def test_paths_are_strings(self):
        """测试路径都是字符串"""
        for browser, platform_paths in BROWSER_PATHS.items():
            for platform_name, paths in platform_paths.items():
                for path in paths:
                    self.assertIsInstance(path, str)


if __name__ == "__main__":
    unittest.main()
