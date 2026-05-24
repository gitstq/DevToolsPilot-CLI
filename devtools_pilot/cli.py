"""
命令行参数解析模块

使用Python标准库argparse实现CLI命令解析：
- 子命令：launch（启动浏览器）、mcp（启动MCP服务器）、inspect（检查页面）、
  screenshot（截图）、monitor（网络监控）
- 参数：--browser（浏览器选择）、--port（调试端口）、--headless（无头模式）
"""

import argparse
import sys
from typing import List, Optional


def create_parser() -> argparse.ArgumentParser:
    """
    创建CLI参数解析器

    Returns:
        配置好的ArgumentParser实例
    """
    parser = argparse.ArgumentParser(
        prog="devtools-pilot",
        description="DevToolsPilot-CLI - 轻量级终端Chrome DevTools智能控制引擎",
        epilog="示例: devtools-pilot launch --browser chrome --port 9222",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version="DevToolsPilot-CLI v0.1.0",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="禁用彩色输出",
    )

    parser.add_argument(
        "--verbose", "-V",
        action="store_true",
        default=False,
        help="启用详细日志输出",
    )

    # 全局可选参数
    parser.add_argument(
        "--browser", "-b",
        choices=["chrome", "edge", "brave", "firefox"],
        default=None,
        help="选择浏览器 (默认: 自动检测)",
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="远程调试端口 (默认: 9222)",
    )

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="调试服务器主机地址 (默认: localhost)",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="使用无头模式",
    )

    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=None,
        help="默认超时时间（秒）",
    )

    # 子命令
    subparsers = parser.add_subparsers(
        dest="command",
        title="可用命令",
        description="DevToolsPilot-CLI 提供以下子命令",
        metavar="COMMAND",
    )

    # ============================================================
    # launch 命令
    # ============================================================
    launch_parser = subparsers.add_parser(
        "launch",
        help="启动浏览器并打开远程调试端口",
        description="启动指定的浏览器并开启远程调试端口，等待连接。",
    )
    launch_parser.add_argument(
        "--url", "-u",
        type=str,
        default=None,
        help="启动后导航到的URL",
    )
    launch_parser.add_argument(
        "--window-size",
        type=str,
        default=None,
        help="窗口大小，格式: WIDTHxHEIGHT (如 1920x1080)",
    )
    launch_parser.add_argument(
        "--user-data-dir",
        type=str,
        default=None,
        help="用户数据目录路径",
    )
    launch_parser.add_argument(
        "--extra-args",
        type=str,
        nargs="*",
        default=None,
        help="额外的浏览器启动参数",
    )
    launch_parser.add_argument(
        "--no-wait",
        action="store_true",
        default=False,
        help="不等待用户输入，启动后立即返回",
    )

    # ============================================================
    # mcp 命令
    # ============================================================
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="启动MCP协议服务器",
        description="启动MCP (Model Context Protocol) 服务器，通过stdio与AI模型交互。",
    )
    mcp_parser.add_argument(
        "--screenshot-dir",
        type=str,
        default="./screenshots",
        help="截图保存目录",
    )

    # ============================================================
    # inspect 命令
    # ============================================================
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="检查页面信息",
        description="连接到已运行的浏览器，检查当前页面的信息。",
    )
    inspect_parser.add_argument(
        "--action", "-a",
        choices=["info", "dom", "cookies", "metrics", "console"],
        default="info",
        help="检查类型 (默认: info)",
    )
    inspect_parser.add_argument(
        "--selector", "-s",
        type=str,
        default=None,
        help="CSS选择器（用于DOM操作）",
    )
    inspect_parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出文件路径",
    )
    inspect_parser.add_argument(
        "--json", "-j",
        action="store_true",
        default=False,
        help="以JSON格式输出",
    )

    # ============================================================
    # screenshot 命令
    # ============================================================
    screenshot_parser = subparsers.add_parser(
        "screenshot",
        help="截取页面截图",
        description="连接到已运行的浏览器并截取页面截图。",
    )
    screenshot_parser.add_argument(
        "--type",
        choices=["viewport", "full", "element"],
        default="viewport",
        help="截图类型 (默认: viewport)",
    )
    screenshot_parser.add_argument(
        "--selector", "-s",
        type=str,
        default=None,
        help="元素CSS选择器（type为element时使用）",
    )
    screenshot_parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出文件路径",
    )
    screenshot_parser.add_argument(
        "--format", "-f",
        choices=["png", "jpeg"],
        default="png",
        help="图片格式 (默认: png)",
    )
    screenshot_parser.add_argument(
        "--quality", "-q",
        type=int,
        default=80,
        help="JPEG质量 0-100 (默认: 80)",
    )
    screenshot_parser.add_argument(
        "--base64",
        action="store_true",
        default=False,
        help="输出Base64编码而非保存文件",
    )

    # ============================================================
    # monitor 命令
    # ============================================================
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="网络流量监控",
        description="连接到已运行的浏览器，监控和录制网络请求。",
    )
    monitor_parser.add_argument(
        "--duration", "-d",
        type=int,
        default=0,
        help="监控持续时间（秒），0表示持续监控直到手动停止",
    )
    monitor_parser.add_argument(
        "--filter", "-F",
        type=str,
        default=None,
        help="URL过滤模式（支持通配符*）",
    )
    monitor_parser.add_argument(
        "--export-har",
        type=str,
        default=None,
        help="导出HAR文件路径",
    )
    monitor_parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="实时显示请求流",
    )
    monitor_parser.add_argument(
        "--summary",
        action="store_true",
        default=False,
        help="结束时显示统计摘要",
    )

    # ============================================================
    # eval 命令
    # ============================================================
    eval_parser = subparsers.add_parser(
        "eval",
        help="执行JavaScript代码",
        description="连接到已运行的浏览器，在页面上下文中执行JavaScript代码。",
    )
    eval_parser.add_argument(
        "expression",
        type=str,
        nargs="?",
        default=None,
        help="要执行的JavaScript表达式",
    )
    eval_parser.add_argument(
        "--file", "-f",
        type=str,
        default=None,
        help="从文件读取JavaScript代码",
    )
    eval_parser.add_argument(
        "--no-await",
        action="store_true",
        default=False,
        help="不等待Promise解析",
    )

    # ============================================================
    # detect 命令
    # ============================================================
    detect_parser = subparsers.add_parser(
        "detect",
        help="检测系统中已安装的浏览器",
        description="扫描系统，检测所有已安装的受支持浏览器。",
    )

    return parser


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    解析命令行参数

    Args:
        args: 参数列表，None则使用sys.argv

    Returns:
        解析后的参数命名空间
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    # 如果没有指定子命令，显示帮助
    if parsed.command is None:
        parser.print_help()
        sys.exit(0)

    return parsed
