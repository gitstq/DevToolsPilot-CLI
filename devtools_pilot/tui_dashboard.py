"""
TUI仪表盘模块

提供基于ANSI颜色和文本的终端用户界面：
- 实时状态面板（浏览器状态、当前URL、网络请求数、控制台消息数）
- 交互式命令提示
- 进度条和状态指示器
- 彩色日志输出
- 表格数据展示
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .config import Colors


# ============================================================
# 终端工具
# ============================================================

class Terminal:
    """
    终端工具类

    提供终端尺寸检测、光标控制和清屏功能。
    """

    @staticmethod
    def get_size() -> Tuple[int, int]:
        """
        获取终端尺寸

        Returns:
            (列数, 行数) 元组
        """
        try:
            size = os.get_terminal_size()
            return (size.columns, size.lines)
        except (OSError, ValueError):
            return (80, 24)

    @staticmethod
    def clear_screen() -> None:
        """清屏并将光标移到左上角"""
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    @staticmethod
    def move_cursor(row: int, col: int = 0) -> None:
        """
        移动光标到指定位置

        Args:
            row: 行号（从0开始）
            col: 列号（从0开始）
        """
        sys.stdout.write(f"\033[{row + 1};{col + 1}H")
        sys.stdout.flush()

    @staticmethod
    def hide_cursor() -> None:
        """隐藏光标"""
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    @staticmethod
    def show_cursor() -> None:
        """显示光标"""
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    @staticmethod
    def clear_line() -> None:
        """清除当前行"""
        sys.stdout.write("\033[2K\r")
        sys.stdout.flush()

    @staticmethod
    def save_cursor() -> None:
        """保存光标位置"""
        sys.stdout.write("\033[s")
        sys.stdout.flush()

    @staticmethod
    def restore_cursor() -> None:
        """恢复光标位置"""
        sys.stdout.write("\033[u")
        sys.stdout.flush()

    @staticmethod
    def supports_color() -> bool:
        """
        检测终端是否支持颜色

        Returns:
            是否支持ANSI颜色
        """
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("TERM") == "dumb":
            return False
        if sys.platform == "win32":
            return os.environ.get("ANSICON") is not None or "WT_SESSION" in os.environ
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


# ============================================================
# 文本表格
# ============================================================

class TextTable:
    """
    文本表格渲染器

    在终端中以表格形式展示数据。

    Example:
        >>> table = TextTable(["Name", "Value", "Status"])
        >>> table.add_row(["Chrome", "9222", "Running"])
        >>> table.add_row(["Edge", "9223", "Stopped"])
        >>> print(table.render())
    """

    def __init__(
        self,
        headers: List[str],
        column_widths: Optional[List[int]] = None,
        padding: int = 2,
    ):
        """
        初始化表格

        Args:
            headers: 表头列表
            column_widths: 列宽列表，None则自动计算
            padding: 单元格内边距
        """
        self.headers = headers
        self.rows: List[List[str]] = []
        self.column_widths = column_widths or []
        self.padding = padding
        self._header_color = Colors.BOLD + Colors.CYAN
        self._border_color = Colors.DIM
        self._row_colors: Optional[List[str]] = None

    def add_row(self, row: List[str], color: Optional[str] = None) -> None:
        """
        添加数据行

        Args:
            row: 行数据列表
            color: 行颜色代码
        """
        self.rows.append(row)

    def set_row_colors(self, colors: List[str]) -> None:
        """
        设置行颜色

        Args:
            colors: 颜色代码列表，与行一一对应
        """
        self._row_colors = colors

    def _calculate_widths(self) -> List[int]:
        """计算各列宽度"""
        if self.column_widths:
            return self.column_widths

        widths = [len(h) for h in self.headers]
        for row in self.rows:
            for i, cell in enumerate(row):
                cell_len = len(str(cell))
                if i < len(widths):
                    widths[i] = max(widths[i], cell_len)
                else:
                    widths.append(cell_len)

        return widths

    def render(self) -> str:
        """
        渲染表格为字符串

        Returns:
            表格字符串
        """
        widths = self._calculate_widths()
        pad = " " * self.padding
        lines = []

        # 表头
        header_cells = []
        for i, h in enumerate(self.headers):
            w = widths[i] if i < len(widths) else len(h)
            header_cells.append(f"{pad}{h:<{w}}{pad}")
        header_line = f"{self._border_color}|{Colors.RESET}" + (
            f"{self._border_color}|{Colors.RESET}".join(header_cells)
        ) + f"{self._border_color}|{Colors.RESET}"
        lines.append(header_line)

        # 分隔线
        sep_cells = []
        for w in widths:
            sep_cells.append(f"{self._border_color}{'-' * (w + self.padding * 2)}{Colors.RESET}")
        sep_line = f"{self._border_color}+{Colors.RESET}" + (
            f"{self._border_color}+{Colors.RESET}".join(sep_cells)
        ) + f"{self._border_color}+{Colors.RESET}"
        lines.append(sep_line)

        # 数据行
        for row_idx, row in enumerate(self.rows):
            row_color = ""
            if self._row_colors and row_idx < len(self._row_colors):
                row_color = self._row_colors[row_idx]

            cells = []
            for i, cell in enumerate(row):
                w = widths[i] if i < len(widths) else len(str(cell))
                cell_str = str(cell)
                if len(cell_str) > w:
                    cell_str = cell_str[:w - 3] + "..."
                cells.append(f"{pad}{row_color}{cell_str:<{w}}{Colors.RESET}{pad}")

            row_line = f"{self._border_color}|{Colors.RESET}" + (
                f"{self._border_color}|{Colors.RESET}".join(cells)
            ) + f"{self._border_color}|{Colors.RESET}"
            lines.append(row_line)

        return "\n".join(lines)


# ============================================================
# 状态指示器
# ============================================================

class StatusIndicator:
    """
    状态指示器

    用彩色符号表示不同状态。

    Attributes:
        status: 状态字符串
    """

    SYMBOLS = {
        "running": (f"{Colors.GREEN}[RUNNING]{Colors.RESET}", Colors.GREEN),
        "stopped": (f"{Colors.RED}[STOPPED]{Colors.RESET}", Colors.RED),
        "error": (f"{Colors.RED}[ERROR]{Colors.RESET}", Colors.RED),
        "warning": (f"{Colors.YELLOW}[WARNING]{Colors.RESET}", Colors.YELLOW),
        "pending": (f"{Colors.YELLOW}[PENDING]{Colors.RESET}", Colors.YELLOW),
        "success": (f"{Colors.GREEN}[OK]{Colors.RESET}", Colors.GREEN),
        "loading": (f"{Colors.CYAN}[LOADING]{Colors.RESET}", Colors.CYAN),
        "connected": (f"{Colors.GREEN}[CONNECTED]{Colors.RESET}", Colors.GREEN),
        "disconnected": (f"{Colors.RED}[DISCONNECTED]{Colors.RESET}", Colors.RED),
    }

    @classmethod
    def get(cls, status: str) -> str:
        """
        获取状态指示文本

        Args:
            status: 状态名称

        Returns:
            带颜色的状态文本
        """
        return cls.SYMBOLS.get(status.lower(), f"[{status.upper()}]")

    @classmethod
    def spinner_frame(cls, frame: int = 0) -> str:
        """
        获取加载动画帧

        Args:
            frame: 帧编号

        Returns:
            动画字符
        """
        frames = ["-", "\\", "|", "/"]
        return f"{Colors.CYAN}{frames[frame % len(frames)]}{Colors.RESET}"


# ============================================================
# 进度条
# ============================================================

class TUIProgressBar:
    """
    TUI进度条组件

    在终端中显示彩色进度条。

    Example:
        >>> bar = TUIProgressBar(total=100, label="Downloading")
        >>> bar.update(50)
        >>> bar.finish()
    """

    def __init__(
        self,
        total: int,
        label: str = "",
        width: int = 30,
        fill_char: str = "#",
        empty_char: str = "-",
    ):
        self.total = total
        self.label = label
        self.width = width
        self.fill_char = fill_char
        self.empty_char = empty_char
        self.current = 0
        self.start_time = time.time()

    def update(self, current: int) -> None:
        """
        更新进度条

        Args:
            current: 当前进度
        """
        self.current = min(current, self.total)
        self._render()

    def _render(self) -> None:
        """渲染进度条"""
        if self.total <= 0:
            return

        progress = self.current / self.total
        filled = int(self.width * progress)
        empty = self.width - filled

        # 计算百分比和ETA
        percent = progress * 100
        elapsed = time.time() - self.start_time
        if progress > 0:
            eta = elapsed / progress - elapsed
            eta_str = f"ETA: {eta:.1f}s"
        else:
            eta_str = ""

        # 颜色选择
        if progress >= 1.0:
            bar_color = Colors.GREEN
        elif progress >= 0.7:
            bar_color = Colors.CYAN
        elif progress >= 0.3:
            bar_color = Colors.YELLOW
        else:
            bar_color = Colors.RED

        bar = (
            f"{self.label} "
            f"{bar_color}[{self.fill_char * filled}{Colors.DIM}{self.empty_char * empty}{bar_color}]{Colors.RESET} "
            f"{percent:5.1f}% "
            f"{self.current}/{self.total} "
            f"{eta_str}"
        )

        sys.stdout.write(f"\r{bar}")
        sys.stdout.flush()

    def finish(self) -> None:
        """完成进度条"""
        self.update(self.total)
        sys.stdout.write("\n")
        sys.stdout.flush()


# ============================================================
# TUI仪表盘
# ============================================================

class TUIDashboard:
    """
    TUI仪表盘

    提供实时状态面板，显示浏览器控制引擎的运行状态。

    Attributes:
        browser_status: 浏览器状态
        current_url: 当前URL
        network_count: 网络请求数
        console_count: 控制台消息数
        errors_count: 错误数

    Example:
        >>> dashboard = TUIDashboard()
        >>> dashboard.browser_status = "running"
        >>> dashboard.current_url = "https://example.com"
        >>> dashboard.render()
    """

    def __init__(self, refresh_interval: float = 1.0):
        """
        初始化仪表盘

        Args:
            refresh_interval: 刷新间隔（秒）
        """
        self.refresh_interval = refresh_interval
        self.browser_status: str = "stopped"
        self.current_url: str = ""
        self.page_title: str = ""
        self.network_count: int = 0
        self.console_count: int = 0
        self.errors_count: int = 0
        self.memory_usage: str = ""
        self.start_time: float = time.time()
        self._running = False
        self._spinner_frame = 0

    def _get_header(self) -> str:
        """获取仪表盘头部"""
        width = Terminal.get_size()[0]
        title = " DevToolsPilot-CLI "
        padding = (width - len(title) - 4) // 2

        return (
            f"\n"
            f"{Colors.BOLD}{Colors.BLUE}{'=' * width}{Colors.RESET}\n"
            f"{Colors.BOLD}{Colors.BLUE}{' ' * padding}{title}{' ' * (width - len(title) - padding * 2)}{Colors.RESET}\n"
            f"{Colors.BOLD}{Colors.BLUE}{'=' * width}{Colors.RESET}\n"
        )

    def _get_status_panel(self) -> str:
        """获取状态面板"""
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)

        status = StatusIndicator.get(self.browser_status)
        url_display = self.current_url or "N/A"
        if len(url_display) > 50:
            url_display = url_display[:47] + "..."

        title_display = self.page_title or "N/A"
        if len(title_display) > 40:
            title_display = title_display[:37] + "..."

        lines = [
            f"\n{Colors.BOLD}  Status Panel{Colors.RESET}",
            f"  {Colors.DIM}{'-' * 40}{Colors.RESET}",
            f"  Browser:     {status}",
            f"  URL:         {Colors.CYAN}{url_display}{Colors.RESET}",
            f"  Title:       {Colors.WHITE}{title_display}{Colors.RESET}",
            f"  Requests:    {Colors.GREEN}{self.network_count}{Colors.RESET}",
            f"  Console:     {Colors.YELLOW}{self.console_count}{Colors.RESET}",
            f"  Errors:      {Colors.RED}{self.errors_count}{Colors.RESET}",
            f"  Uptime:      {hours:02d}:{minutes:02d}:{seconds:02d}",
        ]

        return "\n".join(lines)

    def _get_command_hint(self) -> str:
        """获取命令提示"""
        return (
            f"\n{Colors.DIM}  Available commands: "
            f"navigate <url> | screenshot | eval <js> | "
            f"dom <selector> | stats | quit{Colors.RESET}"
        )

    def render(self) -> None:
        """渲染完整仪表盘"""
        output = (
            self._get_header()
            + self._get_status_panel()
            + self._get_command_hint()
            + "\n"
        )
        sys.stdout.write(output)
        sys.stdout.flush()

    def render_update(self) -> None:
        """渲染更新（不清屏）"""
        self._spinner_frame += 1
        status = StatusIndicator.spinner_frame(self._spinner_frame)
        url_display = self.current_url[:40] if self.current_url else "N/A"

        line = (
            f"\r  {status} "
            f"URL: {Colors.CYAN}{url_display:<40}{Colors.RESET} "
            f"Req: {Colors.GREEN}{self.network_count}{Colors.RESET} "
            f"Con: {Colors.YELLOW}{self.console_count}{Colors.RESET} "
            f"Err: {Colors.RED}{self.errors_count}{Colors.RESET} "
        )
        sys.stdout.write(line)
        sys.stdout.flush()

    def clear_update(self) -> None:
        """清除更新行"""
        Terminal.clear_line()

    @staticmethod
    def print_banner() -> None:
        """打印启动横幅"""
        banner = f"""
{Colors.BOLD}{Colors.CYAN}
   ____                  _       ____  ____
  / __ \\____ ___  ____  (_)_  __/ __ \\/ __/
 / / / / __ `__ \\/ __ \\/ / |/_/ / / /\\__ \\
/ /_/ / / / / / / / / / />  </ /_/ /___/ /
\\____/_/ /_/ /_/_/ /_/_/_/|_|\\____//____/
{Colors.RESET}
{Colors.DIM}  Lightweight Terminal Chrome DevTools Control Engine{Colors.RESET}
{Colors.DIM}  Version 0.1.0 | Python {sys.version.split()[0]}{Colors.RESET}
"""
        sys.stdout.write(banner)
        sys.stdout.flush()

    @staticmethod
    def print_section(title: str) -> None:
        """
        打印分节标题

        Args:
            title: 标题文本
        """
        sys.stdout.write(
            f"\n{Colors.BOLD}{Colors.BLUE}--- {title} ---{Colors.RESET}\n"
        )
        sys.stdout.flush()

    @staticmethod
    def print_kv(key: str, value: str, value_color: str = Colors.WHITE) -> None:
        """
        打印键值对

        Args:
            key: 键名
            value: 值
            value_color: 值的颜色
        """
        sys.stdout.write(
            f"  {Colors.DIM}{key:<20}{Colors.RESET}{value_color}{value}{Colors.RESET}\n"
        )
        sys.stdout.flush()

    @staticmethod
    def print_log(level: str, message: str) -> None:
        """
        打印日志消息

        Args:
            level: 日志级别
            message: 消息内容
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        level_colors = {
            "INFO": Colors.BLUE,
            "WARN": Colors.YELLOW,
            "ERROR": Colors.RED,
            "DEBUG": Colors.DIM,
            "SUCCESS": Colors.GREEN,
        }

        color = level_colors.get(level.upper(), Colors.WHITE)
        sys.stdout.write(
            f"  {Colors.DIM}{timestamp}{Colors.RESET} "
            f"{color}[{level:<7}]{Colors.RESET} "
            f"{message}\n"
        )
        sys.stdout.flush()
