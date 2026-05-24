"""
MCP协议服务器模块

实现Model Context Protocol (MCP) 服务器，通过stdio传输与AI模型交互：
- MCP协议stdio传输
- 提供tools：navigate、screenshot、execute_js、get_dom、get_network_requests、click_element
- JSON-RPC消息处理
- 资源和提示词管理

MCP协议允许AI模型通过标准化接口控制浏览器，
实现网页浏览、数据提取、自动化测试等功能。
"""

import asyncio
import json
import logging
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import MCP_PROTOCOL_VERSION, MCP_SERVER_NAME, MCP_SERVER_VERSION
from .cdp_client import CDPClient
from .page_controller import PageController
from .network_monitor import NetworkMonitor
from .screenshot_engine import ScreenshotEngine

logger = logging.getLogger(__name__)


# ============================================================
# MCP协议消息类型
# ============================================================

class MCPMessage:
    """MCP协议消息基类"""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        raise NotImplementedError


class MCPRequest:
    """
    MCP JSON-RPC请求

    Attributes:
        jsonrpc: JSON-RPC版本（固定为 "2.0"）
        id: 请求ID
        method: 方法名
        params: 参数
    """

    def __init__(self, id: Any, method: str, params: Optional[Dict[str, Any]] = None):
        self.jsonrpc = "2.0"
        self.id = id
        self.method = method
        self.params = params or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
            "params": self.params,
        }


class MCPResponse:
    """
    MCP JSON-RPC响应

    Attributes:
        jsonrpc: JSON-RPC版本
        id: 对应请求的ID
        result: 成功结果
        error: 错误信息
    """

    def __init__(
        self,
        id: Any,
        result: Optional[Any] = None,
        error: Optional[Dict[str, Any]] = None,
    ):
        self.jsonrpc = "2.0"
        self.id = id
        self.result = result
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        response: Dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return response


class MCPNotification:
    """
    MCP JSON-RPC通知（无ID，不需要响应）

    Attributes:
        jsonrpc: JSON-RPC版本
        method: 方法名
        params: 参数
    """

    def __init__(self, method: str, params: Optional[Dict[str, Any]] = None):
        self.jsonrpc = "2.0"
        self.method = method
        self.params = params or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
        }


# ============================================================
# MCP工具定义
# ============================================================

class MCPTool:
    """
    MCP工具定义

    Attributes:
        name: 工具名称
        description: 工具描述
        input_schema: 输入参数JSON Schema
        handler: 处理函数
    """

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable,
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


# ============================================================
# MCP服务器
# ============================================================

class MCPServer:
    """
    MCP协议服务器

    通过stdio传输实现MCP协议，提供浏览器控制工具给AI模型使用。

    支持的MCP方法：
    - initialize: 初始化连接
    - tools/list: 列出可用工具
    - tools/call: 调用工具
    - resources/list: 列出可用资源
    - resources/read: 读取资源
    - ping: 心跳检测

    Attributes:
        client: CDP客户端
        page: 页面控制器
        network: 网络监控器
        screenshot: 截图引擎
        tools: 已注册的工具列表

    Example:
        >>> server = MCPServer(port=9222)
        >>> await server.run()
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9222,
        headless: bool = False,
        browser: str = "chrome",
        screenshot_dir: str = "./screenshots",
    ):
        """
        初始化MCP服务器

        Args:
            host: 调试服务器主机
            port: 调试端口
            headless: 无头模式
            browser: 浏览器名称
            screenshot_dir: 截图目录
        """
        self.host = host
        self.port = port
        self.headless = headless
        self.browser = browser
        self.screenshot_dir = screenshot_dir

        self.client: Optional[CDPClient] = None
        self.page: Optional[PageController] = None
        self.network: Optional[NetworkMonitor] = None
        self.screenshot_engine: Optional[ScreenshotEngine] = None

        self.tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self._server_info = {
            "name": MCP_SERVER_NAME,
            "version": MCP_SERVER_VERSION,
        }
        self._protocol_version = MCP_PROTOCOL_VERSION

        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """注册默认工具集"""
        self.register_tool(MCPTool(
            name="navigate",
            description="导航到指定URL。等待页面加载完成后返回。",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要导航到的URL",
                    },
                    "wait_until": {
                        "type": "string",
                        "enum": ["load", "domcontentloaded", "none"],
                        "description": "等待条件，默认为load",
                        "default": "load",
                    },
                },
                "required": ["url"],
            },
            handler=self._tool_navigate,
        ))

        self.register_tool(MCPTool(
            name="screenshot",
            description="截取当前页面截图。支持全页面截图和元素截图。",
            input_schema={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["viewport", "full_page", "element"],
                        "description": "截图类型",
                        "default": "viewport",
                    },
                    "selector": {
                        "type": "string",
                        "description": "元素CSS选择器（type为element时必填）",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["png", "jpeg"],
                        "description": "图片格式",
                        "default": "png",
                    },
                    "quality": {
                        "type": "integer",
                        "description": "JPEG质量 (0-100)",
                        "default": 80,
                    },
                    "return_base64": {
                        "type": "boolean",
                        "description": "是否返回Base64编码",
                        "default": True,
                    },
                },
            },
            handler=self._tool_screenshot,
        ))

        self.register_tool(MCPTool(
            name="execute_js",
            description="在页面上下文中执行JavaScript代码并返回结果。",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "JavaScript表达式或代码",
                    },
                    "await_promise": {
                        "type": "boolean",
                        "description": "是否等待Promise解析",
                        "default": True,
                    },
                },
                "required": ["expression"],
            },
            handler=self._tool_execute_js,
        ))

        self.register_tool(MCPTool(
            name="get_dom",
            description="获取页面DOM信息。可以获取整个文档或指定元素的内容。",
            input_schema={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS选择器，默认获取整个文档",
                    },
                    "property": {
                        "type": "string",
                        "enum": ["html", "text", "attribute", "value"],
                        "description": "要获取的属性",
                        "default": "text",
                    },
                    "attribute_name": {
                        "type": "string",
                        "description": "当property为attribute时，指定属性名",
                    },
                },
            },
            handler=self._tool_get_dom,
        ))

        self.register_tool(MCPTool(
            name="get_network_requests",
            description="获取网络请求记录和统计信息。",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["statistics", "list", "har"],
                        "description": "操作类型：statistics=统计, list=请求列表, har=HAR格式",
                        "default": "statistics",
                    },
                    "filter_method": {
                        "type": "string",
                        "description": "按HTTP方法过滤",
                    },
                    "filter_domain": {
                        "type": "string",
                        "description": "按域名过滤",
                    },
                    "filter_status": {
                        "type": "integer",
                        "description": "按状态码过滤",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制",
                        "default": 50,
                    },
                },
            },
            handler=self._tool_get_network_requests,
        ))

        self.register_tool(MCPTool(
            name="click_element",
            description="点击页面上的元素。",
            input_schema={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "要点击的元素的CSS选择器",
                    },
                },
                "required": ["selector"],
            },
            handler=self._tool_click_element,
        ))

        self.register_tool(MCPTool(
            name="get_page_info",
            description="获取当前页面的基本信息（URL、标题、Cookie等）。",
            input_schema={
                "type": "object",
                "properties": {},
            },
            handler=self._tool_get_page_info,
        ))

        self.register_tool(MCPTool(
            name="type_text",
            description="在指定输入框中输入文本。",
            input_schema={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "输入框的CSS选择器",
                    },
                    "text": {
                        "type": "string",
                        "description": "要输入的文本",
                    },
                },
                "required": ["selector", "text"],
            },
            handler=self._tool_type_text,
        ))

    def register_tool(self, tool: MCPTool) -> None:
        """
        注册工具

        Args:
            tool: MCPTool实例
        """
        self.tools[tool.name] = tool

    async def _ensure_connected(self) -> bool:
        """确保已连接到CDP"""
        if self.client and self.client.connected:
            return True

        try:
            self.client = CDPClient(
                host=self.host,
                port=self.port,
            )
            await self.client.connect()

            # 初始化各模块
            self.page = PageController(self.client)
            await self.page.enable()

            self.network = NetworkMonitor(self.client)
            await self.network.enable()

            self.screenshot_engine = ScreenshotEngine(
                self.client,
                output_dir=self.screenshot_dir,
            )

            return True
        except Exception as e:
            logger.error(f"连接CDP失败: {e}")
            return False

    # ============================================================
    # 工具处理函数
    # ============================================================

    async def _tool_navigate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """导航工具"""
        url = params.get("url", "")
        wait_until = params.get("wait_until", "load")

        if not url:
            return {"success": False, "error": "URL不能为空"}

        # 自动补全协议
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url

        result = await self.page.goto(url, wait_until=wait_until)
        title = await self.page.get_title()
        return {
            "success": result.get("success", False),
            "url": self.page.current_url,
            "title": title,
        }

    async def _tool_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """截图工具"""
        shot_type = params.get("type", "viewport")
        selector = params.get("selector")
        fmt = params.get("format", "png")
        quality = params.get("quality", 80)
        return_b64 = params.get("return_base64", True)

        if shot_type == "full_page":
            result = await self.screenshot_engine.capture_full_page(
                format=fmt, quality=quality, return_base64=return_b64,
            )
        elif shot_type == "element" and selector:
            result = await self.screenshot_engine.capture_element(
                selector=selector, format=fmt, quality=quality, return_base64=return_b64,
            )
        else:
            result = await self.screenshot_engine.capture_viewport(
                format=fmt, quality=quality, return_base64=return_b64,
            )

        if result and return_b64:
            return {
                "success": True,
                "data": result,
                "format": fmt,
                "type": shot_type,
            }
        elif result:
            return {
                "success": True,
                "filepath": result,
                "format": fmt,
                "type": shot_type,
            }
        else:
            return {"success": False, "error": "截图失败"}

    async def _tool_execute_js(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行JS工具"""
        expression = params.get("expression", "")
        await_promise = params.get("await_promise", True)

        if not expression:
            return {"success": False, "error": "表达式不能为空"}

        try:
            result = await self.page.evaluate(expression, await_promise=await_promise)
            return {
                "success": True,
                "result": result,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_get_dom(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取DOM工具"""
        selector = params.get("selector")
        prop = params.get("property", "text")
        attr_name = params.get("attribute_name", "")

        try:
            if not selector:
                # 获取整个文档
                html = await self.page.get_page_content()
                return {
                    "success": True,
                    "html": html[:100000],  # 限制大小
                    "truncated": len(html) > 100000,
                }

            if prop == "html":
                content = await self.page.get_inner_html(selector)
            elif prop == "text":
                content = await self.page.get_text_content(selector)
            elif prop == "attribute":
                content = await self.page.get_attribute(selector, attr_name)
            elif prop == "value":
                content = await self.page.evaluate(
                    f"document.querySelector({selector!r})?.value"
                )
            else:
                content = await self.page.get_text_content(selector)

            return {
                "success": True,
                "selector": selector,
                "property": prop,
                "content": str(content) if content is not None else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_get_network_requests(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取网络请求工具"""
        action = params.get("action", "statistics")
        filter_method = params.get("filter_method")
        filter_domain = params.get("filter_domain")
        filter_status = params.get("filter_status")
        limit = params.get("limit", 50)

        if action == "statistics":
            stats = self.network.get_statistics()
            return {"success": True, "statistics": stats}
        elif action == "list":
            requests = self.network.get_filtered_requests(
                method=filter_method,
                domain=filter_domain,
                status_code=filter_status,
            )
            return {
                "success": True,
                "total": len(requests),
                "requests": [r.to_dict() for r in requests[:limit]],
            }
        elif action == "har":
            har = self.network.export_har()
            return {"success": True, "har": har}
        else:
            return {"success": False, "error": f"未知操作: {action}"}

    async def _tool_click_element(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """点击元素工具"""
        selector = params.get("selector", "")
        if not selector:
            return {"success": False, "error": "选择器不能为空"}

        success = await self.page.click_element(selector)
        return {"success": success}

    async def _tool_get_page_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取页面信息工具"""
        url = await self.page.get_url()
        title = await self.page.get_title()
        cookies = await self.page.get_cookies()

        return {
            "success": True,
            "url": url,
            "title": title,
            "cookieCount": len(cookies),
            "cookies": [
                {"name": c.get("name"), "domain": c.get("domain"), "value": c.get("value", "")[:50]}
                for c in cookies[:20]
            ],
        }

    async def _tool_type_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """输入文本工具"""
        selector = params.get("selector", "")
        text = params.get("text", "")

        if not selector or not text:
            return {"success": False, "error": "selector和text不能为空"}

        success = await self.page.type_text(selector, text)
        return {"success": success}

    # ============================================================
    # JSON-RPC消息处理
    # ============================================================

    def _parse_message(self, line: str) -> Optional[Tuple[Dict[str, Any], bool]]:
        """
        解析JSON-RPC消息

        Args:
            line: JSON字符串

        Returns:
            (消息字典, 是否为通知) 元组，解析失败返回None
        """
        try:
            data = json.loads(line)
            if not isinstance(data, dict):
                return None
            is_notification = "id" not in data
            return (data, is_notification)
        except json.JSONDecodeError:
            return None

    async def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理JSON-RPC请求

        Args:
            request: 请求字典

        Returns:
            响应字典
        """
        request_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        try:
            if method == "initialize":
                self._initialized = True
                return MCPResponse(
                    id=request_id,
                    result={
                        "protocolVersion": self._protocol_version,
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False},
                        },
                        "serverInfo": self._server_info,
                    },
                ).to_dict()

            elif method == "notifications/initialized":
                # 通知，不需要响应
                return MCPResponse(id=request_id, result={}).to_dict()

            elif method == "ping":
                return MCPResponse(id=request_id, result={}).to_dict()

            elif method == "tools/list":
                tools_list = [tool.to_dict() for tool in self.tools.values()]
                return MCPResponse(
                    id=request_id,
                    result={"tools": tools_list},
                ).to_dict()

            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})

                tool = self.tools.get(tool_name)
                if not tool:
                    return MCPResponse(
                        id=request_id,
                        error={
                            "code": -32601,
                            "message": f"未知工具: {tool_name}",
                        },
                    ).to_dict()

                # 确保已连接
                if not await self._ensure_connected():
                    return MCPResponse(
                        id=request_id,
                        error={
                            "code": -32000,
                            "message": "无法连接到浏览器",
                        },
                    ).to_dict()

                # 调用工具
                try:
                    result = await tool.handler(tool_args)
                    return MCPResponse(
                        id=request_id,
                        result={
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, ensure_ascii=False, default=str),
                                }
                            ],
                        },
                    ).to_dict()
                except Exception as e:
                    return MCPResponse(
                        id=request_id,
                        error={
                            "code": -32000,
                            "message": f"工具执行错误: {str(e)}",
                        },
                    ).to_dict()

            elif method == "resources/list":
                return MCPResponse(
                    id=request_id,
                    result={"resources": list(self._resources.values())},
                ).to_dict()

            elif method == "resources/read":
                resource_uri = params.get("uri", "")
                resource = self._resources.get(resource_uri)
                if resource:
                    return MCPResponse(
                        id=request_id,
                        result={
                            "contents": [
                                {
                                    "uri": resource_uri,
                                    "mimeType": resource.get("mimeType", "text/plain"),
                                    "text": resource.get("text", ""),
                                }
                            ]
                        },
                    ).to_dict()
                else:
                    return MCPResponse(
                        id=request_id,
                        error={
                            "code": -32601,
                            "message": f"未知资源: {resource_uri}",
                        },
                    ).to_dict()

            else:
                return MCPResponse(
                    id=request_id,
                    error={
                        "code": -32601,
                        "message": f"未知方法: {method}",
                    },
                ).to_dict()

        except Exception as e:
            logger.error(f"处理请求时出错: {e}")
            return MCPResponse(
                id=request_id,
                error={
                    "code": -32603,
                    "message": f"内部错误: {str(e)}",
                },
            ).to_dict()

    async def _write_response(self, response: Dict[str, Any]) -> None:
        """
        将响应写入stdout

        Args:
            response: 响应字典
        """
        try:
            line = json.dumps(response, ensure_ascii=False)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            pass

    async def run(self) -> None:
        """
        启动MCP服务器主循环

        从stdin读取JSON-RPC请求，处理后写入stdout响应。
        """
        logger.info("MCP服务器启动 (stdio传输)")

        # 写入服务器就绪日志到stderr（不影响stdio通信）
        sys.stderr.write(f"DevToolsPilot MCP Server v{MCP_SERVER_VERSION}\n")
        sys.stderr.write(f"连接目标: {self.host}:{self.port}\n")
        sys.stderr.flush()

        # 主消息循环
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        try:
            while True:
                try:
                    line = await reader.readline()
                    if not line:
                        # EOF，退出
                        break

                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue

                    # 解析并处理消息
                    parsed = self._parse_message(line_str)
                    if parsed is None:
                        continue

                    data, is_notification = parsed

                    if is_notification:
                        # 通知消息，不需要响应
                        continue

                    # 处理请求
                    response = await self._handle_request(data)
                    await self._write_response(response)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"消息处理循环出错: {e}")
                    sys.stderr.write(f"Error: {e}\n")
                    sys.stderr.flush()

        except KeyboardInterrupt:
            pass
        finally:
            # 清理资源
            if self.client:
                await self.client.close()
            sys.stderr.write("MCP服务器已关闭\n")
            sys.stderr.flush()

    async def stop(self) -> None:
        """停止MCP服务器"""
        if self.client:
            await self.client.close()
