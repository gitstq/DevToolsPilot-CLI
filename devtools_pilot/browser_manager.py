"""
浏览器管理器模块

负责浏览器进程的启动、检测和生命周期管理：
- 自动检测系统中已安装的浏览器（Chrome、Edge、Brave、Firefox）
- 以--remote-debugging-port参数启动浏览器
- 跨平台支持（Windows/macOS/Linux）
- 进程生命周期管理
- 优雅关闭
"""

import logging
import os
import platform
import signal
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple

from .config import Config, SUPPORTED_BROWSERS
from .utils import is_port_available, wait_for_port, print_info, print_error, print_warning

logger = logging.getLogger(__name__)


# ============================================================
# 浏览器路径检测
# ============================================================

# 各操作系统上常见浏览器安装路径
BROWSER_PATHS: Dict[str, Dict[str, List[str]]] = {
    "chrome": {
        "Windows": [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ],
        "Darwin": [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ],
        "Linux": [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/snap/bin/chromium",
            "/usr/lib/chromium-browser/chromium-browser",
        ],
    },
    "edge": {
        "Windows": [
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        ],
        "Darwin": [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ],
        "Linux": [
            "/usr/bin/microsoft-edge",
            "/usr/bin/microsoft-edge-stable",
            "/opt/microsoft/msedge/msedge",
        ],
    },
    "brave": {
        "Windows": [
            os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ],
        "Darwin": [
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ],
        "Linux": [
            "/usr/bin/brave-browser",
            "/usr/bin/brave",
            "/snap/bin/brave",
        ],
    },
    "firefox": {
        "Windows": [
            os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"),
        ],
        "Darwin": [
            "/Applications/Firefox.app/Contents/MacOS/firefox",
        ],
        "Linux": [
            "/usr/bin/firefox",
            "/usr/bin/firefox-esr",
        ],
    },
}


class BrowserInfo:
    """
    浏览器信息

    Attributes:
        name: 浏览器名称
        path: 浏览器可执行文件路径
        version: 浏览器版本（如果可获取）
        supports_cdp: 是否支持Chrome DevTools Protocol
    """

    def __init__(
        self,
        name: str,
        path: str,
        version: Optional[str] = None,
        supports_cdp: bool = True,
    ):
        self.name = name
        self.path = path
        self.version = version
        self.supports_cdp = supports_cdp

    def __repr__(self) -> str:
        return (
            f"BrowserInfo(name={self.name!r}, path={self.path!r}, "
            f"version={self.version!r}, supports_cdp={self.supports_cdp})"
        )


class BrowserManager:
    """
    浏览器进程管理器

    管理浏览器进程的检测、启动和关闭。
    支持Chrome、Edge、Brave和Firefox浏览器。

    Attributes:
        config: 配置对象
        process: 当前浏览器进程
        browser_info: 当前使用的浏览器信息

    Example:
        >>> manager = BrowserManager(port=9222, headless=True)
        >>> info = manager.detect_browser("chrome")
        >>> await manager.launch(info)
        >>> await manager.close()
    """

    def __init__(
        self,
        port: int = 9222,
        host: str = "localhost",
        headless: bool = False,
        browser: str = "chrome",
        extra_args: Optional[List[str]] = None,
        user_data_dir: Optional[str] = None,
        window_size: Optional[Tuple[int, int]] = None,
    ):
        """
        初始化浏览器管理器

        Args:
            port: 远程调试端口
            host: 调试服务器主机地址
            headless: 是否使用无头模式
            browser: 浏览器名称
            extra_args: 额外的命令行参数
            user_data_dir: 用户数据目录路径
            window_size: 窗口大小 (width, height)
        """
        self.port = port
        self.host = host
        self.headless = headless
        self.browser_name = browser
        self.extra_args = extra_args or []
        self.user_data_dir = user_data_dir
        self.window_size = window_size

        self.process: Optional[subprocess.Popen] = None
        self.browser_info: Optional[BrowserInfo] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """浏览器进程是否正在运行"""
        if self.process is None:
            return False
        # 检查进程是否仍然存活
        self.process.poll()
        return self.process.returncode is None

    def detect_browser(self, name: Optional[str] = None) -> Optional[BrowserInfo]:
        """
        检测系统中已安装的浏览器

        Args:
            name: 要检测的浏览器名称，None则自动检测

        Returns:
            BrowserInfo对象，未找到返回None
        """
        browser_name = (name or self.browser_name).lower()

        if browser_name not in BROWSER_PATHS:
            print_error(f"不支持的浏览器: {browser_name}")
            print_info(f"支持的浏览器: {', '.join(SUPPORTED_BROWSERS)}")
            return None

        system = platform.system()
        paths = BROWSER_PATHS[browser_name].get(system, [])

        for path in paths:
            if os.path.isfile(path):
                version = self._get_browser_version(path)
                supports_cdp = browser_name != "firefox"
                info = BrowserInfo(
                    name=browser_name,
                    path=path,
                    version=version,
                    supports_cdp=supports_cdp,
                )
                logger.info(f"检测到浏览器: {info}")
                return info

        logger.warning(f"未找到浏览器: {browser_name}")
        return None

    def detect_all_browsers(self) -> List[BrowserInfo]:
        """
        检测系统中所有已安装的浏览器

        Returns:
            BrowserInfo对象列表
        """
        found = []
        for name in SUPPORTED_BROWSERS:
            info = self.detect_browser(name)
            if info:
                found.append(info)
        return found

    def _get_browser_version(self, path: str) -> Optional[str]:
        """
        获取浏览器版本

        Args:
            path: 浏览器可执行文件路径

        Returns:
            版本字符串，获取失败返回None
        """
        try:
            if platform.system() == "Windows":
                # Windows上使用wmic获取版本
                result = subprocess.run(
                    ["wmic", "datafile", "where", f"name='{path.replace(os.sep, os.sep + os.sep)}'",
                     "get", "Version", "/value"],
                    capture_output=True, text=True, timeout=5,
                )
                for line in result.stdout.strip().split("\n"):
                    if "Version=" in line:
                        return line.split("=")[1].strip()
            else:
                # macOS/Linux上直接执行 --version
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                output = result.stdout.strip()
                if output:
                    # 提取版本号
                    parts = output.split()
                    for part in parts:
                        if part[0].isdigit():
                            return part
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug(f"获取浏览器版本失败: {e}")
        return None

    def _build_launch_args(self, info: BrowserInfo) -> List[str]:
        """
        构建浏览器启动参数

        Args:
            info: 浏览器信息

        Returns:
            命令行参数列表
        """
        args = [info.path]

        # 远程调试端口
        args.append(f"--remote-debugging-port={self.port}")

        # 无头模式
        if self.headless:
            if info.name == "firefox":
                args.append("--headless")
            else:
                args.append("--headless=new")

        # 用户数据目录
        if self.user_data_dir:
            args.append(f"--user-data-dir={self.user_data_dir}")
        else:
            # 使用临时目录避免与用户主配置冲突
            import tempfile
            temp_dir = os.path.join(
                tempfile.gettempdir(), f"devtools-pilot-{self.port}"
            )
            args.append(f"--user-data-dir={temp_dir}")

        # 窗口大小
        if self.window_size:
            width, height = self.window_size
            if info.name == "firefox":
                args.append(f"--width={width}")
                args.append(f"--height={height}")
            else:
                args.append(f"--window-size={width},{height}")

        # Chrome/Edge/Brave通用参数
        if info.name != "firefox":
            args.extend([
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-client-side-phishing-detection",
                "--disable-default-apps",
                "--disable-hang-monitor",
                "--disable-popup-blocking",
                "--disable-prompt-on-repost",
                "--disable-sync",
                "--metrics-recording-only",
                "--safebrowsing-disable-auto-update",
            ])

        # 额外参数
        args.extend(self.extra_args)

        # 启动URL（空白页）
        if info.name == "firefox":
            args.append("about:blank")
        else:
            args.append("about:blank")

        return args

    async def launch(
        self,
        browser_info: Optional[BrowserInfo] = None,
        wait_timeout: float = 30.0,
    ) -> bool:
        """
        启动浏览器

        Args:
            browser_info: 浏览器信息，None则自动检测
            wait_timeout: 等待调试端口就绪的超时时间

        Returns:
            是否启动成功

        Raises:
            RuntimeError: 浏览器已在运行或启动失败
        """
        if self.is_running:
            raise RuntimeError("浏览器已在运行中")

        # 检测浏览器
        info = browser_info or self.detect_browser()
        if info is None:
            raise RuntimeError(
                f"未找到浏览器 '{self.browser_name}'，请确认已安装"
            )

        if not info.supports_cdp:
            print_warning(
                f"{info.name} 对CDP的支持有限，部分功能可能不可用"
            )

        self.browser_info = info

        # 检查端口是否可用
        if not is_port_available(self.port, self.host):
            print_error(
                f"端口 {self.port} 已被占用，请使用 --port 参数指定其他端口"
            )
            return False

        # 构建启动参数
        args = self._build_launch_args(info)
        logger.info(f"启动浏览器: {' '.join(args)}")
        print_info(f"启动 {info.name} (端口: {self.port})")

        # 启动进程
        try:
            # Windows上需要特殊处理
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()  # type: ignore
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore
                startupinfo.wShowWindow = 0  # SW_HIDE  # type: ignore

            self.process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
            )
        except FileNotFoundError:
            print_error(f"浏览器可执行文件不存在: {info.path}")
            return False
        except PermissionError:
            print_error(f"没有权限执行: {info.path}")
            return False
        except OSError as e:
            print_error(f"启动浏览器失败: {e}")
            return False

        self._is_running = True

        # 等待调试端口就绪
        print_info("等待调试端口就绪...")
        if wait_for_port(self.port, self.host, timeout=wait_timeout):
            print_info(f"调试端口 {self.port} 已就绪")
            return True
        else:
            print_error(
                f"调试端口 {self.port} 在 {wait_timeout}s 内未就绪"
            )
            await self.close()
            return False

    async def close(self, force: bool = False, timeout: float = 10.0) -> bool:
        """
        关闭浏览器进程

        Args:
            force: 是否强制关闭
            timeout: 等待优雅关闭的超时时间

        Returns:
            是否关闭成功
        """
        if self.process is None:
            return True

        logger.info("正在关闭浏览器...")

        if not force:
            try:
                # 尝试优雅关闭
                if platform.system() == "Windows":
                    # Windows上使用taskkill
                    subprocess.run(
                        ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                        capture_output=True, timeout=5,
                    )
                else:
                    # Unix上发送SIGTERM
                    self.process.send_signal(signal.SIGTERM)

                # 等待进程退出
                try:
                    self.process.wait(timeout=timeout)
                    print_info("浏览器已优雅关闭")
                    self._cleanup()
                    return True
                except subprocess.TimeoutExpired:
                    print_warning("优雅关闭超时，尝试强制关闭")
            except (ProcessLookupError, OSError) as e:
                logger.debug(f"优雅关闭失败: {e}")

        # 强制关闭
        if force or self.process.poll() is None:
            try:
                self.process.kill()
                self.process.wait(timeout=5)
                print_info("浏览器已强制关闭")
            except (ProcessLookupError, OSError):
                pass

        self._cleanup()
        return True

    def _cleanup(self) -> None:
        """清理资源"""
        self.process = None
        self._is_running = False

        # 清理临时用户数据目录（如果使用的是默认临时目录）
        if self.user_data_dir is None:
            import tempfile
            temp_dir = os.path.join(
                tempfile.gettempdir(), f"devtools-pilot-{self.port}"
            )
            try:
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError:
                pass

    def get_debug_url(self) -> str:
        """
        获取调试服务器URL

        Returns:
            调试服务器HTTP URL
        """
        return f"http://{self.host}:{self.port}"

    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        return (
            f"BrowserManager(browser={self.browser_name!r}, "
            f"port={self.port}, status={status})"
        )
