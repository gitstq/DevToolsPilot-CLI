"""
CLI入口模块

DevToolsPilot-CLI 的主入口点，负责：
- 解析命令行参数
- 根据子命令调度到对应的处理函数
- 管理异步事件循环
- 处理全局错误

用法:
    python -m devtools_pilot launch --browser chrome --port 9222
    python -m devtools_pilot mcp --port 9222
    python -m devtools_pilot inspect --action info
    python -m devtools_pilot screenshot --type full
    python -m devtools_pilot monitor --duration 60
    python -m devtools_pilot eval "document.title"
    python -m devtools_pilot detect
"""

import asyncio
import json
import logging
import os
import signal
import sys

from . import __version__
from .browser_manager import BrowserManager
from .cdp_client import CDPClient, CDPError
from .cli import parse_args
from .config import Config, Colors
from .console_capture import ConsoleCapture, LogLevel
from .mcp_server import MCPServer
from .network_monitor import NetworkMonitor
from .page_controller import PageController
from .screenshot_engine import ScreenshotEngine
from .tui_dashboard import TUIDashboard, TextTable, StatusIndicator
from .utils import (
    ensure_dir,
    format_size,
    format_duration,
    print_colored,
    print_error,
    print_info,
    print_success,
    print_warning,
    safe_json_dumps,
)


# ============================================================
# 日志配置
# ============================================================

def setup_logging(verbose: bool = False) -> None:
    """
    配置日志系统

    Args:
        verbose: 是否启用详细日志
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,  # 日志输出到stderr，不影响stdout的MCP通信
    )


# ============================================================
# 命令处理函数
# ============================================================

async def cmd_launch(args, config: Config) -> int:
    """
    处理launch命令 - 启动浏览器

    Args:
        args: 命令行参数
        config: 配置对象

    Returns:
        退出码
    """
    TUIDashboard.print_banner()

    # 解析窗口大小
    window_size = None
    if args.window_size:
        try:
            parts = args.window_size.lower().split("x")
            window_size = (int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            print_error(f"无效的窗口大小格式: {args.window_size}，应为 WIDTHxHEIGHT")
            return 1

    # 创建浏览器管理器
    manager = BrowserManager(
        port=config.debug_port,
        host=config.host,
        headless=config.headless,
        browser=config.browser,
        extra_args=args.extra_args,
        user_data_dir=args.user_data_dir,
        window_size=window_size,
    )

    # 检测浏览器
    print_info(f"检测浏览器: {config.browser}")
    browser_info = manager.detect_browser()
    if browser_info is None:
        print_error(f"未找到浏览器: {config.browser}")
        print_info("使用 'devtools-pilot detect' 查看可用浏览器")
        return 1

    print_success(f"找到浏览器: {browser_info.path}")
    if browser_info.version:
        print_info(f"版本: {browser_info.version}")

    # 启动浏览器
    print_info(f"启动浏览器 (端口: {config.debug_port})...")
    success = await manager.launch(browser_info)
    if not success:
        print_error("浏览器启动失败")
        return 1

    print_success("浏览器已启动")
    print_info(f"调试地址: http://{config.host}:{config.debug_port}")
    print_info(f"调试面板: http://{config.host}:{config.debug_port}/json")

    # 如果指定了URL，导航到该URL
    if args.url:
        try:
            client = CDPClient(host=config.host, port=config.debug_port)
            await client.connect()
            page = PageController(client)
            await page.enable()
            print_info(f"导航到: {args.url}")
            result = await page.goto(args.url)
            if result.get("success"):
                title = await page.get_title()
                print_success(f"页面标题: {title}")
            await client.close()
        except Exception as e:
            print_warning(f"导航失败: {e}")

    if args.no_wait:
        print_info("浏览器已在后台运行")
        return 0

    # 等待用户输入
    print_info("按 Ctrl+C 停止浏览器...")
    try:
        while manager.is_running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print_info("\n正在关闭浏览器...")

    await manager.close()
    print_success("浏览器已关闭")
    return 0


async def cmd_mcp(args, config: Config) -> int:
    """
    处理mcp命令 - 启动MCP服务器

    Args:
        args: 命令行参数
        config: 配置对象

    Returns:
        退出码
    """
    server = MCPServer(
        host=config.host,
        port=config.debug_port,
        headless=config.headless,
        browser=config.browser,
        screenshot_dir=args.screenshot_dir,
    )

    await server.run()
    return 0


async def cmd_inspect(args, config: Config) -> int:
    """
    处理inspect命令 - 检查页面信息

    Args:
        args: 命令行参数
        config: 配置对象

    Returns:
        退出码
    """
    # 连接到浏览器
    try:
        client = CDPClient(host=config.host, port=config.debug_port)
        await client.connect()
    except ConnectionError as e:
        print_error(f"无法连接到浏览器: {e}")
        print_info("请确保浏览器已启动并开启了远程调试端口")
        return 1

    page = PageController(client)
    await page.enable()

    result_data = {}

    try:
        if args.action == "info":
            # 获取页面基本信息
            url = await page.get_url()
            title = await page.get_title()
            cookies = await page.get_cookies()
            metrics = await page.get_page_metrics()

            TUIDashboard.print_section("页面信息")
            TUIDashboard.print_kv("URL", url, Colors.CYAN)
            TUIDashboard.print_kv("标题", title, Colors.WHITE)
            TUIDashboard.print_kv("Cookie数", str(len(cookies)), Colors.YELLOW)

            result_data = {
                "url": url,
                "title": title,
                "cookieCount": len(cookies),
                "cookies": cookies,
                "metrics": metrics,
            }

        elif args.action == "dom":
            # 获取DOM信息
            if args.selector:
                text = await page.get_text_content(args.selector)
                html = await page.get_inner_html(args.selector)
                TUIDashboard.print_section(f"DOM - {args.selector}")
                TUIDashboard.print_kv("文本内容", str(text or "")[:500], Colors.WHITE)
                TUIDashboard.print_kv("HTML", str(html or "")[:500], Colors.DIM)
                result_data = {"selector": args.selector, "text": text, "html": html}
            else:
                content = await page.get_page_content()
                TUIDashboard.print_section("页面HTML")
                print(content[:2000])
                if len(content) > 2000:
                    print_warning(f"... 已截断，总长度: {len(content)} 字符")
                result_data = {"html": content[:100000]}

        elif args.action == "cookies":
            # 获取Cookie
            cookies = await page.get_cookies()
            TUIDashboard.print_section("Cookies")

            if cookies:
                table = TextTable(["名称", "域名", "路径", "值", "安全", "HttpOnly"])
                for c in cookies[:30]:
                    table.add_row([
                        c.get("name", ""),
                        c.get("domain", ""),
                        c.get("path", ""),
                        str(c.get("value", ""))[:30],
                        str(c.get("secure", False)),
                        str(c.get("httpOnly", False)),
                    ])
                print(table.render())
                if len(cookies) > 30:
                    print_warning(f"... 共 {len(cookies)} 个Cookie，仅显示前30个")
            else:
                print_info("没有Cookie")

            result_data = {"cookies": cookies}

        elif args.action == "metrics":
            # 获取性能指标
            metrics = await page.get_page_metrics()
            TUIDashboard.print_section("性能指标")
            for m in metrics:
                name = m.get("name", "")
                value = m.get("value", 0)
                TUIDashboard.print_kv(name, str(value), Colors.CYAN)
            result_data = {"metrics": metrics}

        elif args.action == "console":
            # 获取控制台消息
            console = ConsoleCapture(client)
            await console.enable()
            print_info("监听控制台消息中... (按Ctrl+C停止)")
            try:
                while True:
                    msgs = console.get_messages(limit=10)
                    for msg in msgs:
                        level_colors = {
                            "log": Colors.WHITE,
                            "info": Colors.BLUE,
                            "warning": Colors.YELLOW,
                            "error": Colors.RED,
                            "debug": Colors.DIM,
                        }
                        color = level_colors.get(msg.level.value, Colors.WHITE)
                        print_colored(
                            f"  [{msg.level.value.upper()}] {msg.text[:200]}",
                            color,
                        )
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass

            stats = console.get_statistics()
            result_data = {"statistics": stats}
            await console.disable()

    except CDPError as e:
        print_error(f"CDP错误: {e}")
        result_data = {"error": str(e)}
    finally:
        await client.close()

    # JSON输出
    if args.json and result_data:
        output = safe_json_dumps(result_data)
        if args.output:
            ensure_dir(args.output)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print_success(f"结果已保存到: {args.output}")
        else:
            print(output)

    return 0


async def cmd_screenshot(args, config: Config) -> int:
    """
    处理screenshot命令 - 截图

    Args:
        args: 命令行参数
        config: 配置对象

    Returns:
        退出码
    """
    # 连接到浏览器
    try:
        client = CDPClient(host=config.host, port=config.debug_port)
        await client.connect()
    except ConnectionError as e:
        print_error(f"无法连接到浏览器: {e}")
        return 1

    engine = ScreenshotEngine(client, output_dir=config.screenshot_dir)

    try:
        if args.type == "full":
            print_info("正在截取全页面截图...")
            result = await engine.capture_full_page(
                format=args.format,
                quality=args.quality,
                filepath=args.output,
                return_base64=args.base64,
            )
        elif args.type == "element":
            if not args.selector:
                print_error("元素截图需要指定 --selector 参数")
                await client.close()
                return 1
            print_info(f"正在截取元素截图: {args.selector}")
            result = await engine.capture_element(
                selector=args.selector,
                format=args.format,
                quality=args.quality,
                filepath=args.output,
                return_base64=args.base64,
            )
        else:
            print_info("正在截取视口截图...")
            result = await engine.capture_viewport(
                format=args.format,
                quality=args.quality,
                filepath=args.output,
                return_base64=args.base64,
            )

        if result:
            if args.base64:
                print(result[:100] + "..." if len(result) > 100 else result)
            else:
                print_success(f"截图已保存: {result}")
                file_size = os.path.getsize(result) if os.path.exists(result) else 0
                print_info(f"文件大小: {format_size(file_size)}")
        else:
            print_error("截图失败")
            await client.close()
            return 1

    except CDPError as e:
        print_error(f"截图失败: {e}")
        await client.close()
        return 1

    await client.close()
    return 0


async def cmd_monitor(args, config: Config) -> int:
    """
    处理monitor命令 - 网络监控

    Args:
        args: 命令行参数
        config: 配置对象

    Returns:
        退出码
    """
    # 连接到浏览器
    try:
        client = CDPClient(host=config.host, port=config.debug_port)
        await client.connect()
    except ConnectionError as e:
        print_error(f"无法连接到浏览器: {e}")
        return 1

    monitor = NetworkMonitor(client)
    await monitor.enable()

    if args.filter:
        monitor.add_filter(args.filter)
        print_info(f"URL过滤: {args.filter}")

    print_info("网络监控已启动... (按Ctrl+C停止)")

    # 实时显示回调
    if args.live:
        async def on_request(params):
            req = params if isinstance(params, dict) else {}
            url = req.get("url", "")
            method = req.get("method", "GET")
            print_colored(f"  >> {method} {url[:80]}", Colors.DIM)

        monitor.client.on("Network.requestWillBeSent", on_request)

    try:
        if args.duration > 0:
            await asyncio.sleep(args.duration)
        else:
            while True:
                await asyncio.sleep(1)
                # 显示实时统计
                stats = monitor.get_statistics()
                sys.stderr.write(
                    f"\r  请求: {stats['totalRequests']} | "
                    f"大小: {stats.get('totalSizeFormatted', '0 B')} | "
                    f"失败: {stats['failedRequests']} | "
                    f"缓存: {stats['cachedRequests']}   "
                )
                sys.stderr.flush()
    except KeyboardInterrupt:
        pass

    sys.stderr.write("\n")

    # 显示统计摘要
    if args.summary or args.duration > 0:
        stats = monitor.get_statistics()
        TUIDashboard.print_section("网络请求统计")
        TUIDashboard.print_kv("总请求数", str(stats["totalRequests"]), Colors.CYAN)
        TUIDashboard.print_kv("总大小", stats.get("totalSizeFormatted", "0 B"), Colors.CYAN)
        TUIDashboard.print_kv("总耗时", stats.get("totalDurationFormatted", "0s"), Colors.CYAN)
        TUIDashboard.print_kv("平均耗时", stats.get("averageDurationFormatted", "0s"), Colors.CYAN)
        TUIDashboard.print_kv("失败请求", str(stats["failedRequests"]), Colors.RED)
        TUIDashboard.print_kv("缓存请求", str(stats["cachedRequests"]), Colors.GREEN)

        # 按域名统计
        by_domain = stats.get("byDomain", {})
        if by_domain:
            print(f"\n  {Colors.BOLD}按域名统计:{Colors.RESET}")
            table = TextTable(["域名", "请求数"])
            for domain, count in list(by_domain.items())[:10]:
                table.add_row([domain, str(count)])
            print(table.render())

        # 按方法统计
        by_method = stats.get("byMethod", {})
        if by_method:
            print(f"\n  {Colors.BOLD}按方法统计:{Colors.RESET}")
            for method, count in by_method.items():
                print_colored(f"  {method}: {count}", Colors.CYAN)

    # 导出HAR
    if args.export_har:
        har_json = monitor.export_har_json()
        ensure_dir(args.export_har)
        with open(args.export_har, "w", encoding="utf-8") as f:
            f.write(har_json)
        print_success(f"HAR文件已导出: {args.export_har}")

    await monitor.disable()
    await client.close()
    return 0


async def cmd_eval(args, config: Config) -> int:
    """
    处理eval命令 - 执行JavaScript

    Args:
        args: 命令行参数
        config: 配置对象

    Returns:
        退出码
    """
    # 获取要执行的代码
    expression = args.expression
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                expression = f.read()
        except FileNotFoundError:
            print_error(f"文件不存在: {args.file}")
            return 1
    elif expression is None:
        print_error("请指定要执行的JavaScript表达式或使用 --file 参数")
        return 1

    # 连接到浏览器
    try:
        client = CDPClient(host=config.host, port=config.debug_port)
        await client.connect()
    except ConnectionError as e:
        print_error(f"无法连接到浏览器: {e}")
        return 1

    page = PageController(client)
    await page.enable()

    try:
        result = await page.evaluate(
            expression,
            await_promise=not args.no_await,
        )
        print_success("执行结果:")
        print(safe_json_dumps(result, indent=2))
    except CDPError as e:
        print_error(f"执行失败: {e}")
        await client.close()
        return 1
    except Exception as e:
        print_error(f"未知错误: {e}")
        await client.close()
        return 1

    await client.close()
    return 0


async def cmd_detect(args, config: Config) -> int:
    """
    处理detect命令 - 检测浏览器

    Args:
        args: 命令行参数
        config: 配置对象

    Returns:
        退出码
    """
    TUIDashboard.print_banner()
    TUIDashboard.print_section("浏览器检测")

    manager = BrowserManager()
    browsers = manager.detect_all_browsers()

    if browsers:
        table = TextTable(["浏览器", "路径", "版本", "CDP支持"])
        colors = []
        for info in browsers:
            table.add_row([
                info.name,
                info.path,
                info.version or "未知",
                "是" if info.supports_cdp else "有限",
            ])
            colors.append(Colors.GREEN if info.supports_cdp else Colors.YELLOW)
        table.set_row_colors(colors)
        print(table.render())
        print_success(f"检测到 {len(browsers)} 个浏览器")
    else:
        print_warning("未检测到任何受支持的浏览器")
        print_info("支持的浏览器: Chrome, Edge, Brave, Firefox")

    return 0


# ============================================================
# 命令调度
# ============================================================

COMMAND_HANDLERS = {
    "launch": cmd_launch,
    "mcp": cmd_mcp,
    "inspect": cmd_inspect,
    "screenshot": cmd_screenshot,
    "monitor": cmd_monitor,
    "eval": cmd_eval,
    "detect": cmd_detect,
}


async def main(args=None) -> int:
    """
    CLI主函数

    Args:
        args: 命令行参数，None则使用sys.argv

    Returns:
        退出码
    """
    parsed = parse_args(args)

    # 配置日志
    setup_logging(parsed.verbose)

    # 创建配置
    config = Config(
        debug_port=parsed.port,
        host=parsed.host,
        timeout=parsed.timeout,
        headless=parsed.headless,
        browser=parsed.browser,
        no_color=parsed.no_color,
    )

    # 调度到对应的命令处理函数
    handler = COMMAND_HANDLERS.get(parsed.command)
    if handler is None:
        print_error(f"未知命令: {parsed.command}")
        return 1

    try:
        return await handler(parsed, config)
    except KeyboardInterrupt:
        print_info("\n操作已取消")
        return 130
    except Exception as e:
        print_error(f"未预期的错误: {e}")
        if parsed.verbose:
            import traceback
            traceback.print_exc()
        return 1


def entry_point() -> None:
    """CLI入口点（同步包装）"""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    entry_point()
