"""
工具函数模块

提供项目中通用的工具函数，包括：
- WebSocket通信辅助
- JSON处理
- 时间格式化
- 文件操作
- URL处理
- ANSI终端输出辅助
"""

import base64
import json
import os
import re
import socket
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union


# ============================================================
# 时间相关工具
# ============================================================

def timestamp_ms() -> int:
    """
    获取当前时间的毫秒级时间戳

    Returns:
        毫秒级Unix时间戳
    """
    return int(time.time() * 1000)


def timestamp_to_datetime(ts: float) -> datetime:
    """
    将时间戳转换为datetime对象

    Args:
        ts: Unix时间戳（秒或毫秒）

    Returns:
        datetime对象
    """
    # 如果时间戳大于10^12，认为是毫秒级
    if ts > 1e12:
        ts = ts / 1000.0
    return datetime.fromtimestamp(ts)


def format_duration(seconds: float) -> str:
    """
    格式化持续时间

    Args:
        seconds: 持续时间（秒）

    Returns:
        格式化的时间字符串，如 "1h 23m 45s" 或 "123ms"
    """
    if seconds < 0.001:
        return f"{seconds * 1000000:.0f}us"
    elif seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_datetime(dt: Optional[datetime] = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化日期时间

    Args:
        dt: datetime对象，默认为当前时间
        fmt: 格式字符串

    Returns:
        格式化的时间字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


# ============================================================
# JSON相关工具
# ============================================================

def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    安全的JSON解析，解析失败返回默认值

    Args:
        text: JSON字符串
        default: 解析失败时的默认返回值

    Returns:
        解析后的Python对象或默认值
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def safe_json_dumps(obj: Any, indent: int = 2) -> str:
    """
    安全的JSON序列化

    Args:
        obj: 要序列化的对象
        indent: 缩进空格数

    Returns:
        JSON字符串
    """
    try:
        return json.dumps(obj, indent=indent, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(obj)


# ============================================================
# URL相关工具
# ============================================================

def parse_url(url: str) -> Dict[str, Optional[str]]:
    """
    解析URL，返回各组成部分

    Args:
        url: 要解析的URL字符串

    Returns:
        包含scheme, netloc, path, params, query, fragment的字典
    """
    parsed = urllib.parse.urlparse(url)
    return {
        "scheme": parsed.scheme,
        "netloc": parsed.netloc,
        "path": parsed.path,
        "params": parsed.params,
        "query": parsed.query,
        "fragment": parsed.fragment,
    }


def get_domain(url: str) -> str:
    """
    从URL中提取域名

    Args:
        url: URL字符串

    Returns:
        域名字符串
    """
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc or ""


def url_match_pattern(url: str, pattern: str) -> bool:
    """
    检查URL是否匹配给定的模式（支持通配符*）

    Args:
        url: 要检查的URL
        pattern: 匹配模式，*为通配符

    Returns:
        是否匹配
    """
    # 将通配符模式转换为正则表达式
    regex_pattern = re.escape(pattern).replace(r"\*", ".*")
    return bool(re.fullmatch(regex_pattern, url))


def build_url(base: str, path: str = "", params: Optional[Dict[str, str]] = None) -> str:
    """
    构建完整的URL

    Args:
        base: 基础URL
        path: 路径部分
        params: 查询参数字典

    Returns:
        完整的URL字符串
    """
    url = urllib.parse.urljoin(base, path)
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"
    return url


# ============================================================
# 文件相关工具
# ============================================================

def ensure_dir(filepath: str) -> str:
    """
    确保文件所在目录存在，不存在则创建

    Args:
        filepath: 文件路径

    Returns:
        文件路径
    """
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    return filepath


def generate_filename(prefix: str = "screenshot", extension: str = "png") -> str:
    """
    生成带时间戳的唯一文件名

    Args:
        prefix: 文件名前缀
        extension: 文件扩展名

    Returns:
        生成的文件名
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefix}_{timestamp}.{extension}"


def save_base64_to_file(base64_data: str, filepath: str) -> str:
    """
    将Base64编码的数据保存为文件

    Args:
        base64_data: Base64编码的字符串
        filepath: 目标文件路径

    Returns:
        保存的文件路径
    """
    ensure_dir(filepath)
    with open(filepath, "wb") as f:
        f.write(base64.b64decode(base64_data))
    return filepath


def file_to_base64(filepath: str) -> str:
    """
    将文件读取为Base64编码字符串

    Args:
        filepath: 文件路径

    Returns:
        Base64编码字符串
    """
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ============================================================
# 网络相关工具
# ============================================================

def is_port_available(port: int, host: str = "localhost") -> bool:
    """
    检查端口是否可用

    Args:
        port: 端口号
        host: 主机地址

    Returns:
        端口是否可用
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result != 0  # 0表示端口被占用
    except (socket.error, OSError):
        return True


def wait_for_port(port: int, host: str = "localhost", timeout: float = 30.0) -> bool:
    """
    等待端口可用（有服务监听）

    Args:
        port: 端口号
        host: 主机地址
        timeout: 超时时间（秒）

    Returns:
        是否在超时前端口变为可用
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex((host, port))
                if result == 0:
                    return True
        except (socket.error, OSError):
            pass
        time.sleep(0.1)
    return False


# ============================================================
# ANSI终端输出工具
# ============================================================

def colorize(text: str, color_code: str) -> str:
    """
    为文本添加ANSI颜色

    Args:
        text: 要着色的文本
        color_code: ANSI颜色代码

    Returns:
        着色后的文本
    """
    return f"{color_code}{text}\033[0m"


def print_colored(text: str, color_code: str, file: Any = None) -> None:
    """
    打印带颜色的文本

    Args:
        text: 要打印的文本
        color_code: ANSI颜色代码
        file: 输出文件对象
    """
    if file is None:
        file = sys.stdout
    file.write(f"{color_code}{text}\033[0m\n")
    file.flush()


def print_success(message: str) -> None:
    """打印成功消息（绿色）"""
    from .config import Colors
    print_colored(f"  [OK] {message}", Colors.GREEN)


def print_error(message: str) -> None:
    """打印错误消息（红色）"""
    from .config import Colors
    print_colored(f"  [ERROR] {message}", Colors.RED)


def print_warning(message: str) -> None:
    """打印警告消息（黄色）"""
    from .config import Colors
    print_colored(f"  [WARN] {message}", Colors.YELLOW)


def print_info(message: str) -> None:
    """打印信息消息（蓝色）"""
    from .config import Colors
    print_colored(f"  [INFO] {message}", Colors.BLUE)


def print_debug(message: str) -> None:
    """打印调试消息（灰色）"""
    from .config import Colors
    print_colored(f"  [DEBUG] {message}", Colors.DIM)


# ============================================================
# 进度条工具
# ============================================================

class ProgressBar:
    """
    简单的终端进度条

    使用ANSI转义序列在终端中显示进度条。

    Attributes:
        total: 总数量
        width: 进度条宽度（字符数）
        current: 当前进度
    """

    def __init__(self, total: int, width: int = 40, prefix: str = ""):
        """
        初始化进度条

        Args:
            total: 总数量
            width: 进度条宽度
            prefix: 进度条前缀文本
        """
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0
        self.start_time = time.time()

    def update(self, current: Optional[int] = None) -> None:
        """
        更新进度条

        Args:
            current: 当前进度值，默认自动递增
        """
        if current is not None:
            self.current = current
        else:
            self.current += 1

        if self.total <= 0:
            return

        progress = min(self.current / self.total, 1.0)
        filled = int(self.width * progress)
        empty = self.width - filled

        # 计算已用时间和预估剩余时间
        elapsed = time.time() - self.start_time
        if progress > 0:
            eta = elapsed / progress - elapsed
            eta_str = format_duration(eta)
        else:
            eta_str = "--"

        bar = f"{self.prefix} [{('#' * filled) + ('-' * empty)}] {self.current}/{self.total} ETA: {eta_str}"
        # 使用回车符覆盖当前行
        sys.stdout.write(f"\r{bar}")
        sys.stdout.flush()

        if self.current >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def finish(self) -> None:
        """完成进度条"""
        self.update(self.total)


# ============================================================
# 数据大小格式化
# ============================================================

def format_size(size_bytes: int) -> str:
    """
    格式化文件/数据大小

    Args:
        size_bytes: 字节数

    Returns:
        人类可读的大小字符串
    """
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    size = float(size_bytes)
    while size >= 1024.0 and index < len(units) - 1:
        size /= 1024.0
        index += 1
    return f"{size:.1f} {units[index]}"


# ============================================================
# 截断工具
# ============================================================

def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


# ============================================================
# HTTP状态码工具
# ============================================================

def http_status_text(code: int) -> str:
    """
    获取HTTP状态码的描述文本

    Args:
        code: HTTP状态码

    Returns:
        状态码描述文本
    """
    status_map = {
        200: "OK",
        201: "Created",
        204: "No Content",
        301: "Moved Permanently",
        302: "Found",
        304: "Not Modified",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        408: "Request Timeout",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }
    return status_map.get(code, "Unknown")
