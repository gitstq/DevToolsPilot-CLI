"""
配置管理模块

管理DevToolsPilot-CLI的所有配置项，包括默认端口、超时时间、
浏览器路径、日志级别等。支持从环境变量和配置文件加载配置。
"""

import json
import os
import platform
from typing import Any, Dict, Optional


# ============================================================
# 默认配置常量
# ============================================================

DEFAULT_DEBUG_PORT = 9222
DEFAULT_HOST = "localhost"
DEFAULT_TIMEOUT = 30  # 秒
DEFAULT_SCREENSHOT_DIR = "./screenshots"
DEFAULT_HAR_DIR = "./har_exports"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # 秒
DEFAULT_PAGE_LOAD_TIMEOUT = 60  # 秒
DEFAULT_NAVIGATION_TIMEOUT = 30  # 秒

# 支持的浏览器名称
SUPPORTED_BROWSERS = ["chrome", "edge", "brave", "firefox"]

# CDP相关常量
CDP_VERSION = "1.3"
CDP_TARGET_TYPE = "page"

# MCP协议常量
MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_NAME = "devtools-pilot"
MCP_SERVER_VERSION = "0.1.0"

# ANSI颜色代码
class Colors:
    """ANSI终端颜色代码"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    @classmethod
    def disable(cls):
        """禁用所有颜色（用于不支持ANSI的终端）"""
        cls.RESET = ""
        cls.BOLD = ""
        cls.DIM = ""
        cls.RED = ""
        cls.GREEN = ""
        cls.YELLOW = ""
        cls.BLUE = ""
        cls.MAGENTA = ""
        cls.CYAN = ""
        cls.WHITE = ""
        cls.BG_RED = ""
        cls.BG_GREEN = ""
        cls.BG_YELLOW = ""
        cls.BG_BLUE = ""


class Config:
    """
    配置管理器

    管理所有运行时配置，支持从环境变量覆盖默认值。
    配置优先级：环境变量 > 构造函数参数 > 默认值

    Attributes:
        debug_port: Chrome远程调试端口
        host: 调试服务器主机地址
        timeout: 默认超时时间（秒）
        headless: 是否使用无头模式
        browser: 默认浏览器名称
        screenshot_dir: 截图保存目录
        har_dir: HAR文件导出目录
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        page_load_timeout: 页面加载超时（秒）
        navigation_timeout: 导航超时（秒）
        no_color: 是否禁用颜色输出
    """

    def __init__(
        self,
        debug_port: Optional[int] = None,
        host: Optional[str] = None,
        timeout: Optional[int] = None,
        headless: bool = False,
        browser: Optional[str] = None,
        screenshot_dir: Optional[str] = None,
        har_dir: Optional[str] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        page_load_timeout: Optional[int] = None,
        navigation_timeout: Optional[int] = None,
        no_color: bool = False,
    ):
        """初始化配置管理器"""
        self.debug_port = debug_port or int(
            os.environ.get("DEVTOOLS_PORT", DEFAULT_DEBUG_PORT)
        )
        self.host = host or os.environ.get("DEVTOOLS_HOST", DEFAULT_HOST)
        self.timeout = timeout or int(
            os.environ.get("DEVTOOLS_TIMEOUT", DEFAULT_TIMEOUT)
        )
        self.headless = headless or os.environ.get(
            "DEVTOOLS_HEADLESS", ""
        ).lower() in ("1", "true", "yes")
        self.browser = browser or os.environ.get(
            "DEVTOOLS_BROWSER", self._detect_default_browser()
        )
        self.screenshot_dir = screenshot_dir or os.environ.get(
            "DEVTOOLS_SCREENSHOT_DIR", DEFAULT_SCREENSHOT_DIR
        )
        self.har_dir = har_dir or os.environ.get(
            "DEVTOOLS_HAR_DIR", DEFAULT_HAR_DIR
        )
        self.max_retries = max_retries or int(
            os.environ.get("DEVTOOLS_MAX_RETRIES", DEFAULT_MAX_RETRIES)
        )
        self.retry_delay = retry_delay or float(
            os.environ.get("DEVTOOLS_RETRY_DELAY", DEFAULT_RETRY_DELAY)
        )
        self.page_load_timeout = page_load_timeout or int(
            os.environ.get("DEVTOOLS_PAGE_LOAD_TIMEOUT", DEFAULT_PAGE_LOAD_TIMEOUT)
        )
        self.navigation_timeout = navigation_timeout or int(
            os.environ.get("DEVTOOLS_NAVIGATION_TIMEOUT", DEFAULT_NAVIGATION_TIMEOUT)
        )
        self.no_color = no_color or os.environ.get(
            "DEVTOOLS_NO_COLOR", ""
        ).lower() in ("1", "true", "yes")

        # 如果禁用颜色，重置颜色代码
        if self.no_color:
            Colors.disable()

    def _detect_default_browser(self) -> str:
        """
        根据当前操作系统检测默认浏览器

        Returns:
            浏览器名称字符串
        """
        system = platform.system()
        if system == "Windows":
            return "edge"
        elif system == "Darwin":
            return "chrome"
        else:
            return "chrome"

    def to_dict(self) -> Dict[str, Any]:
        """
        将配置导出为字典

        Returns:
            包含所有配置项的字典
        """
        return {
            "debug_port": self.debug_port,
            "host": self.host,
            "timeout": self.timeout,
            "headless": self.headless,
            "browser": self.browser,
            "screenshot_dir": self.screenshot_dir,
            "har_dir": self.har_dir,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "page_load_timeout": self.page_load_timeout,
            "navigation_timeout": self.navigation_timeout,
            "no_color": self.no_color,
        }

    def to_json(self, indent: int = 2) -> str:
        """
        将配置导出为JSON字符串

        Args:
            indent: JSON缩进空格数

        Returns:
            JSON格式的配置字符串
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """
        从字典创建配置实例

        Args:
            data: 配置字典

        Returns:
            Config实例
        """
        return cls(**{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames})

    @classmethod
    def from_json(cls, json_str: str) -> "Config":
        """
        从JSON字符串创建配置实例

        Args:
            json_str: JSON格式的配置字符串

        Returns:
            Config实例
        """
        return cls.from_dict(json.loads(json_str))

    def __repr__(self) -> str:
        return (
            f"Config(debug_port={self.debug_port}, host={self.host!r}, "
            f"browser={self.browser!r}, headless={self.headless})"
        )
