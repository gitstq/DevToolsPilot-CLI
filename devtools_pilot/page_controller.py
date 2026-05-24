"""
页面控制器模块

通过CDP协议实现对网页的控制操作：
- 页面导航（goto、reload、back、forward）
- DOM操作（querySelector、querySelectorAll、getAttribute、setProperty）
- JavaScript执行（evaluate）
- Cookie管理
- 页面事件监听
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union

from .cdp_client import CDPClient, CDPError
from .utils import timestamp_ms, truncate

logger = logging.getLogger(__name__)


class PageController:
    """
    页面控制器

    通过CDP协议控制浏览器页面的导航、DOM操作和JavaScript执行。

    Attributes:
        client: CDP客户端实例
        current_url: 当前页面URL
        title: 当前页面标题

    Example:
        >>> client = CDPClient(port=9222)
        >>> await client.connect()
        >>> page = PageController(client)
        >>> await page.goto("https://example.com")
        >>> title = await page.get_title()
        >>> result = await page.evaluate("document.title")
    """

    def __init__(
        self,
        client: CDPClient,
        navigation_timeout: float = 30.0,
    ):
        """
        初始化页面控制器

        Args:
            client: CDP客户端实例
            navigation_timeout: 导航超时时间（秒）
        """
        self.client = client
        self.navigation_timeout = navigation_timeout
        self.current_url: str = ""
        self.title: str = ""
        self._frame_tree_loaded = asyncio.Event()
        self._load_event_fired = asyncio.Event()
        self._dom_content_loaded = asyncio.Event()

        # 注册CDP事件监听
        self._unregister_handlers = []

    async def _setup_event_listeners(self) -> None:
        """设置页面事件监听器"""
        # 页面加载完成事件
        async def on_load_event_fired(params: Dict[str, Any]) -> None:
            self._load_event_fired.set()

        # DOM内容加载完成事件
        async def on_dom_content_loaded(params: Dict[str, Any]) -> None:
            self._dom_content_loaded.set()

        # 帧导航完成事件
        async def on_frame_stopped_loading(params: Dict[str, Any]) -> None:
            self._frame_tree_loaded.set()

        # 帧导航事件
        async def on_frame_navigated(params: Dict[str, Any]) -> None:
            frame = params.get("frame", {})
            if frame.get("parentId") is None:  # 只处理主框架
                self.current_url = frame.get("url", "")

        self._unregister_handlers.append(
            self.client.on("Page.loadEventFired", on_load_event_fired)
        )
        self._unregister_handlers.append(
            self.client.on("Page.domContentEventFired", on_dom_content_loaded)
        )
        self._unregister_handlers.append(
            self.client.on("Page.frameStoppedLoading", on_frame_stopped_loading)
        )
        self._unregister_handlers.append(
            self.client.on("Page.frameNavigated", on_frame_navigated)
        )

    async def enable(self) -> None:
        """启用Page域事件"""
        await self._setup_event_listeners()
        await self.client.send("Page.enable")

        # 获取当前页面信息
        try:
            result = await self.client.send("Page.getFrameTree")
            frame = result.get("frameTree", {}).get("frame", {})
            self.current_url = frame.get("url", "")
        except CDPError:
            pass

    async def disable(self) -> None:
        """禁用Page域事件并清理监听器"""
        try:
            await self.client.send("Page.disable")
        except (CDPError, ConnectionError):
            pass

        for unregister in self._unregister_handlers:
            unregister()
        self._unregister_handlers.clear()

    async def goto(
        self,
        url: str,
        wait_until: str = "load",
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        导航到指定URL

        Args:
            url: 目标URL
            wait_until: 等待条件 ("load", "domcontentloaded", "none")
            timeout: 超时时间（秒）

        Returns:
            导航结果字典

        Raises:
            asyncio.TimeoutError: 导航超时
            CDPError: CDP命令执行失败
        """
        # 重置事件
        self._load_event_fired.clear()
        self._dom_content_loaded.clear()
        self._frame_tree_loaded.clear()

        timeout = timeout or self.navigation_timeout

        # 发送导航命令
        result = await self.client.send(
            "Page.navigate",
            {"url": url},
            timeout=timeout,
        )

        frame_id = result.get("frameId", "")
        error_text = result.get("errorText", "")

        if error_text:
            return {"success": False, "url": url, "error": error_text}

        # 等待导航完成
        if wait_until == "load":
            try:
                await asyncio.wait_for(
                    self._load_event_fired.wait(), timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"导航等待超时: {url}")
        elif wait_until == "domcontentloaded":
            try:
                await asyncio.wait_for(
                    self._dom_content_loaded.wait(), timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"DOM加载等待超时: {url}")
        # "none" 不等待

        # 更新当前URL
        self.current_url = url

        return {"success": True, "url": url, "frame_id": frame_id}

    async def reload(
        self,
        ignore_cache: bool = False,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        重新加载当前页面

        Args:
            ignore_cache: 是否忽略缓存
            timeout: 超时时间

        Returns:
            重新加载结果
        """
        self._load_event_fired.clear()

        await self.client.send(
            "Page.reload",
            {"ignoreCache": ignore_cache},
        )

        timeout = timeout or self.navigation_timeout
        try:
            await asyncio.wait_for(
                self._load_event_fired.wait(), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("页面重新加载超时")

        return {"success": True, "url": self.current_url}

    async def go_back(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        后退到上一页

        Args:
            timeout: 超时时间

        Returns:
            导航结果
        """
        self._load_event_fired.clear()

        result = await self.client.send("Page.goBack")

        timeout = timeout or self.navigation_timeout
        try:
            await asyncio.wait_for(
                self._load_event_fired.wait(), timeout=timeout
            )
        except asyncio.TimeoutError:
            pass

        return result

    async def go_forward(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        前进到下一页

        Args:
            timeout: 超时时间

        Returns:
            导航结果
        """
        self._load_event_fired.clear()

        result = await self.client.send("Page.goForward")

        timeout = timeout or self.navigation_timeout
        try:
            await asyncio.wait_for(
                self._load_event_fired.wait(), timeout=timeout
            )
        except asyncio.TimeoutError:
            pass

        return result

    async def evaluate(
        self,
        expression: str,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """
        在页面上下文中执行JavaScript表达式

        Args:
            expression: JavaScript表达式
            await_promise: 是否等待Promise解析
            return_by_value: 是否按值返回（而非引用）

        Returns:
            JavaScript执行结果

        Raises:
            CDPError: 执行失败
        """
        result = await self.client.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": return_by_value,
                "includeCommandLineAPI": True,
            },
        )

        # 检查异常
        exception_details = result.get("exceptionDetails")
        if exception_details:
            exception = exception_details.get("exception", {})
            description = exception.get("description", "Unknown error")
            raise CDPError(
                -32000,
                f"JavaScript执行错误: {description}"
            )

        # 提取返回值
        result_value = result.get("result", {})
        value = result_value.get("value")
        if value is not None:
            return value

        # 如果是undefined，返回None
        if result_value.get("type") == "undefined":
            return None

        return result_value

    async def query_selector(self, selector: str) -> Optional[Dict[str, Any]]:
        """
        查询匹配选择器的第一个DOM元素

        Args:
            selector: CSS选择器

        Returns:
            RemoteObject字典，未找到返回None
        """
        result = await self.client.send(
            "Runtime.evaluate",
            {
                "expression": f"document.querySelector({json.dumps(selector)})",
                "returnByValue": False,
            },
        )

        remote_object = result.get("result", {})
        if remote_object.get("type") == "undefined" or remote_object.get("subtype") == "null":
            return None

        return remote_object

    async def query_selector_all(self, selector: str) -> List[Dict[str, Any]]:
        """
        查询匹配选择器的所有DOM元素

        Args:
            selector: CSS选择器

        Returns:
            RemoteObject列表
        """
        result = await self.evaluate(
            f"Array.from(document.querySelectorAll({json.dumps(selector)})).length"
        )
        count = int(result) if result else 0

        elements = []
        for i in range(count):
            try:
                elem = await self.client.send(
                    "Runtime.evaluate",
                    {
                        "expression": f"document.querySelectorAll({json.dumps(selector)})[{i}]",
                        "returnByValue": False,
                    },
                )
                elements.append(elem.get("result", {}))
            except CDPError:
                break

        return elements

    async def get_attribute(
        self, selector: str, attribute: str
    ) -> Optional[str]:
        """
        获取元素的属性值

        Args:
            selector: CSS选择器
            attribute: 属性名

        Returns:
            属性值，元素不存在返回None
        """
        result = await self.evaluate(
            f"document.querySelector({json.dumps(selector)})?.getAttribute({json.dumps(attribute)})"
        )
        return str(result) if result is not None else None

    async def set_property(
        self, selector: str, property_name: str, value: str
    ) -> bool:
        """
        设置元素的CSS属性

        Args:
            selector: CSS选择器
            property_name: CSS属性名
            value: 属性值

        Returns:
            是否设置成功
        """
        try:
            await self.evaluate(
                f"document.querySelector({json.dumps(selector)})?.style.setProperty("
                f"{json.dumps(property_name)}, {json.dumps(value)})"
            )
            return True
        except CDPError:
            return False

    async def get_text_content(self, selector: str) -> Optional[str]:
        """
        获取元素的文本内容

        Args:
            selector: CSS选择器

        Returns:
            文本内容
        """
        result = await self.evaluate(
            f"document.querySelector({json.dumps(selector)})?.textContent"
        )
        return str(result) if result is not None else None

    async def get_inner_html(self, selector: str = "body") -> Optional[str]:
        """
        获取元素的innerHTML

        Args:
            selector: CSS选择器，默认为body

        Returns:
            HTML内容
        """
        result = await self.evaluate(
            f"document.querySelector({json.dumps(selector)})?.innerHTML"
        )
        return str(result) if result is not None else None

    async def click_element(self, selector: str) -> bool:
        """
        点击指定元素

        Args:
            selector: CSS选择器

        Returns:
            是否点击成功
        """
        try:
            await self.evaluate(
                f"document.querySelector({json.dumps(selector)})?.click()"
            )
            return True
        except CDPError:
            return False

    async def type_text(
        self, selector: str, text: str, delay: float = 0.05
    ) -> bool:
        """
        在指定元素中输入文本

        Args:
            selector: CSS选择器
            text: 要输入的文本
            delay: 每个字符之间的延迟（秒）

        Returns:
            是否输入成功
        """
        try:
            # 聚焦元素
            await self.evaluate(
                f"document.querySelector({json.dumps(selector)})?.focus()"
            )
            # 逐字符输入
            for char in text:
                await self.client.send("Input.dispatchKeyEvent", {
                    "type": "keyDown",
                    "text": char,
                })
                await asyncio.sleep(delay)
                await self.client.send("Input.dispatchKeyEvent", {
                    "type": "keyUp",
                    "text": char,
                })
            return True
        except CDPError:
            return False

    async def get_title(self) -> str:
        """
        获取当前页面标题

        Returns:
            页面标题
        """
        try:
            result = await self.evaluate("document.title")
            self.title = str(result) if result else ""
        except CDPError:
            pass
        return self.title

    async def get_url(self) -> str:
        """
        获取当前页面URL

        Returns:
            当前URL
        """
        try:
            result = await self.evaluate("window.location.href")
            if result:
                self.current_url = str(result)
        except CDPError:
            pass
        return self.current_url

    async def get_cookies(self) -> List[Dict[str, Any]]:
        """
        获取当前页面的所有Cookie

        Returns:
            Cookie列表
        """
        result = await self.client.send("Network.getAllCookies")
        return result.get("cookies", [])

    async def set_cookie(
        self,
        name: str,
        value: str,
        domain: str = "",
        path: str = "/",
        secure: bool = False,
        http_only: bool = False,
        expires: Optional[float] = None,
    ) -> bool:
        """
        设置Cookie

        Args:
            name: Cookie名称
            value: Cookie值
            domain: 域名
            path: 路径
            secure: 是否安全标志
            http_only: 是否HttpOnly标志
            expires: 过期时间（Unix时间戳）

        Returns:
            是否设置成功
        """
        params: Dict[str, Any] = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "secure": secure,
            "httpOnly": http_only,
        }
        if expires:
            params["expires"] = expires

        result = await self.client.send("Network.setCookie", params)
        return result.get("success", False)

    async def clear_cookies(self) -> bool:
        """
        清除所有Cookie

        Returns:
            是否清除成功
        """
        try:
            await self.client.send("Network.clearBrowserCookies")
            return True
        except CDPError:
            return False

    async def get_page_metrics(self) -> Dict[str, Any]:
        """
        获取页面性能指标

        Returns:
            包含各种性能指标的字典
        """
        try:
            result = await self.client.send("Performance.getMetrics")
            return result.get("metrics", [])
        except CDPError:
            return []

    async def get_document(self) -> Dict[str, Any]:
        """
        获取DOM文档根节点

        Returns:
            DOM节点信息
        """
        result = await self.client.send("DOM.getDocument", {"depth": -1, "pierce": True})
        return result.get("root", {})

    async def get_page_content(self) -> str:
        """
        获取页面完整HTML内容

        Returns:
            HTML字符串
        """
        result = await self.evaluate(
            "document.documentElement.outerHTML"
        )
        return str(result) if result else ""

    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 30.0,
        interval: float = 0.5,
    ) -> bool:
        """
        等待指定选择器的元素出现

        Args:
            selector: CSS选择器
            timeout: 超时时间
            interval: 检查间隔

        Returns:
            元素是否出现
        """
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            try:
                result = await self.evaluate(
                    f"!!document.querySelector({json.dumps(selector)})"
                )
                if result:
                    return True
            except CDPError:
                pass
            await asyncio.sleep(interval)
        return False

    async def add_script_tag(self, url: Optional[str] = None, content: Optional[str] = None) -> bool:
        """
        向页面注入JavaScript脚本

        Args:
            url: 脚本URL
            content: 脚本内容

        Returns:
            是否注入成功
        """
        params: Dict[str, Any] = {}
        if url:
            params["url"] = url
        elif content:
            params["content"] = content
        else:
            return False

        try:
            await self.client.send("Page.addScriptTag", params)
            return True
        except CDPError:
            return False

    async def get_scroll_position(self) -> Dict[str, int]:
        """
        获取页面滚动位置

        Returns:
            包含scrollX和scrollY的字典
        """
        result = await self.evaluate(
            "({x: window.scrollX, y: window.scrollY})"
        )
        if isinstance(result, dict):
            return {"scrollX": int(result.get("x", 0)), "scrollY": int(result.get("y", 0))}
        return {"scrollX": 0, "scrollY": 0}

    async def scroll_to(self, x: int = 0, y: int = 0) -> None:
        """
        滚动页面到指定位置

        Args:
            x: 水平滚动位置
            y: 垂直滚动位置
        """
        await self.evaluate(f"window.scrollTo({x}, {y})")

    def __repr__(self) -> str:
        return f"PageController(url={self.current_url!r}, title={self.title!r})"
