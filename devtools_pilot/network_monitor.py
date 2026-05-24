"""
网络监控器模块

通过CDP的Network域监控HTTP请求/响应：
- HTTP请求/响应录制
- 请求过滤（URL模式匹配）
- 请求统计（按域名、方法、状态码）
- HAR格式导出
"""

import json
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .cdp_client import CDPClient
from .utils import (
    format_duration,
    format_size,
    get_domain,
    http_status_text,
    timestamp_to_datetime,
    timestamp_ms,
    url_match_pattern,
)

logger = logging.getLogger(__name__)


class NetworkRequest:
    """
    单个网络请求的记录

    Attributes:
        request_id: CDP请求ID
        method: HTTP方法
        url: 请求URL
        headers: 请求头
        status_code: HTTP状态码
        status_text: 状态文本
        response_headers: 响应头
        resource_type: 资源类型
        initiator: 请求发起者
        post_data: POST请求数据
        response_body: 响应体（可选）
        request_time: 请求开始时间
        response_time: 响应接收时间
        duration: 请求持续时间（秒）
        encoded_size: 编码后大小
        decoded_size: 解码后大小
        from_cache: 是否来自缓存
        failed: 是否失败
        failure_reason: 失败原因
    """

    def __init__(self, request_id: str):
        self.request_id = request_id
        self.method: str = ""
        self.url: str = ""
        self.headers: Dict[str, str] = {}
        self.status_code: int = 0
        self.status_text: str = ""
        self.response_headers: Dict[str, str] = {}
        self.resource_type: str = ""
        self.initiator: Dict[str, Any] = {}
        self.post_data: Optional[str] = None
        self.response_body: Optional[str] = None
        self.request_time: float = 0.0
        self.response_time: float = 0.0
        self.duration: float = 0.0
        self.encoded_size: int = 0
        self.decoded_size: int = 0
        self.from_cache: bool = False
        self.failed: bool = False
        self.failure_reason: str = ""

    @property
    def domain(self) -> str:
        """请求域名"""
        return get_domain(self.url)

    @property
    def size(self) -> int:
        """响应大小"""
        return max(self.encoded_size, self.decoded_size)

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "requestId": self.request_id,
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "statusCode": self.status_code,
            "statusText": self.status_text,
            "responseHeaders": self.response_headers,
            "resourceType": self.resource_type,
            "initiator": self.initiator,
            "postData": self.post_data,
            "requestTime": self.request_time,
            "responseTime": self.response_time,
            "duration": self.duration,
            "encodedSize": self.encoded_size,
            "decodedSize": self.decoded_size,
            "fromCache": self.from_cache,
            "failed": self.failed,
            "failureReason": self.failure_reason,
        }

    def __repr__(self) -> str:
        status = self.status_code if self.status_code else ("FAILED" if self.failed else "PENDING")
        return f"NetworkRequest({self.method} {self.url[:60]} -> {status})"


class NetworkMonitor:
    """
    网络流量监控器

    通过CDP Network域事件录制和分析HTTP请求/响应。

    Attributes:
        client: CDP客户端实例
        requests: 所有已记录的请求
        is_recording: 是否正在录制

    Example:
        >>> monitor = NetworkMonitor(client)
        >>> await monitor.enable()
        >>> # ... 执行页面操作 ...
        >>> stats = monitor.get_statistics()
        >>> har = monitor.export_har()
    """

    def __init__(self, client: CDPClient):
        """
        初始化网络监控器

        Args:
            client: CDP客户端实例
        """
        self.client = client
        self.requests: List[NetworkRequest] = []
        self._pending_requests: Dict[str, NetworkRequest] = {}
        self._filters: List[str] = []
        self._is_recording = False
        self._unregister_handlers = []
        self._start_time: float = 0.0

    @property
    def is_recording(self) -> bool:
        """是否正在录制"""
        return self._is_recording

    @property
    def total_requests(self) -> int:
        """总请求数"""
        return len(self.requests)

    @property
    def total_size(self) -> int:
        """总传输大小"""
        return sum(r.size for r in self.requests)

    @property
    def failed_requests(self) -> int:
        """失败请求数"""
        return sum(1 for r in self.requests if r.failed)

    @property
    def cached_requests(self) -> int:
        """缓存请求数"""
        return sum(1 for r in self.requests if r.from_cache)

    async def enable(self) -> None:
        """启用网络监控"""
        # 注册事件处理器
        self._unregister_handlers.append(
            self.client.on("Network.requestWillBeSent", self._on_request_will_be_sent)
        )
        self._unregister_handlers.append(
            self.client.on("Network.responseReceived", self._on_response_received)
        )
        self._unregister_handlers.append(
            self.client.on("Network.loadingFinished", self._on_loading_finished)
        )
        self._unregister_handlers.append(
            self.client.on("Network.loadingFailed", self._on_loading_failed)
        )

        # 启用Network域
        await self.client.send("Network.enable", {
            "maxTotalBufferSize": 10 * 1024 * 1024,
            "maxResourceBufferSize": 5 * 1024 * 1024,
        })

        self._is_recording = True
        self._start_time = time.time()
        logger.info("网络监控已启用")

    async def disable(self) -> None:
        """禁用网络监控"""
        self._is_recording = False

        try:
            await self.client.send("Network.disable")
        except Exception:
            pass

        for unregister in self._unregister_handlers:
            unregister()
        self._unregister_handlers.clear()
        logger.info("网络监控已禁用")

    async def _on_request_will_be_sent(self, params: Dict[str, Any]) -> None:
        """处理请求即将发送事件"""
        if not self._is_recording:
            return

        request = params.get("request", {})
        url = request.get("url", "")

        # 应用过滤器
        if self._filters and not any(
            url_match_pattern(url, pattern) for pattern in self._filters
        ):
            return

        req = NetworkRequest(params["requestId"])
        req.method = request.get("method", "GET")
        req.url = url
        req.headers = request.get("headers", {})
        req.post_data = request.get("postData")
        req.resource_type = params.get("type", "")
        req.initiator = params.get("initiator", {})
        req.request_time = params.get("wallTime", time.time())

        self._pending_requests[params["requestId"]] = req

    async def _on_response_received(self, params: Dict[str, Any]) -> None:
        """处理响应接收事件"""
        if not self._is_recording:
            return

        request_id = params["requestId"]
        req = self._pending_requests.get(request_id)
        if req is None:
            return

        response = params.get("response", {})
        req.status_code = response.get("status", 0)
        req.status_text = response.get("statusText", "")
        req.response_headers = response.get("headers", {})
        req.from_cache = response.get("fromDiskCache", False) or response.get("fromServiceWorker", False)
        req.encoded_size = response.get("encodedDataLength", 0)
        req.decoded_size = response.get("content", {}).get("size", 0)
        req.response_time = params.get("timestamp", time.time())

    async def _on_loading_finished(self, params: Dict[str, Any]) -> None:
        """处理加载完成事件"""
        if not self._is_recording:
            return

        request_id = params["requestId"]
        req = self._pending_requests.pop(request_id, None)
        if req is None:
            return

        req.duration = params.get("timestamp", time.time()) - req.request_time
        req.encoded_size = params.get("encodedDataLength", req.encoded_size)

        self.requests.append(req)

    async def _on_loading_failed(self, params: Dict[str, Any]) -> None:
        """处理加载失败事件"""
        if not self._is_recording:
            return

        request_id = params["requestId"]
        req = self._pending_requests.pop(request_id, None)
        if req is None:
            return

        req.failed = True
        req.failure_reason = params.get("errorText", "Unknown error")
        req.duration = params.get("timestamp", time.time()) - req.request_time

        self.requests.append(req)

    def add_filter(self, pattern: str) -> None:
        """
        添加URL过滤模式

        Args:
            pattern: URL匹配模式（支持通配符*）
        """
        self._filters.append(pattern)

    def clear_filters(self) -> None:
        """清除所有过滤器"""
        self._filters.clear()

    def get_filtered_requests(
        self,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        resource_type: Optional[str] = None,
        domain: Optional[str] = None,
        url_pattern: Optional[str] = None,
    ) -> List[NetworkRequest]:
        """
        获取过滤后的请求列表

        Args:
            method: HTTP方法过滤
            status_code: 状态码过滤
            resource_type: 资源类型过滤
            domain: 域名过滤
            url_pattern: URL模式过滤

        Returns:
            过滤后的请求列表
        """
        result = self.requests

        if method:
            result = [r for r in result if r.method.upper() == method.upper()]
        if status_code:
            result = [r for r in result if r.status_code == status_code]
        if resource_type:
            result = [r for r in result if r.resource_type == resource_type]
        if domain:
            result = [r for r in result if domain in r.domain]
        if url_pattern:
            result = [r for r in result if url_match_pattern(r.url, url_pattern)]

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取网络请求统计信息

        Returns:
            包含详细统计的字典
        """
        total = len(self.requests)
        if total == 0:
            return {
                "totalRequests": 0,
                "failedRequests": 0,
                "cachedRequests": 0,
                "totalSize": 0,
                "totalDuration": 0,
                "byDomain": {},
                "byMethod": {},
                "byStatusCode": {},
                "byResourceType": {},
                "averageDuration": 0,
            }

        by_domain: Dict[str, int] = defaultdict(int)
        by_method: Dict[str, int] = defaultdict(int)
        by_status: Dict[str, int] = defaultdict(int)
        by_type: Dict[str, int] = defaultdict(int)

        for req in self.requests:
            by_domain[req.domain] += 1
            by_method[req.method] += 1
            status_key = f"{req.status_code} {http_status_text(req.status_code)}"
            by_status[status_key] += 1
            by_type[req.resource_type or "other"] += 1

        durations = [r.duration for r in self.requests if r.duration > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "totalRequests": total,
            "failedRequests": self.failed_requests,
            "cachedRequests": self.cached_requests,
            "totalSize": self.total_size,
            "totalSizeFormatted": format_size(self.total_size),
            "totalDuration": sum(durations),
            "totalDurationFormatted": format_duration(sum(durations)),
            "averageDuration": avg_duration,
            "averageDurationFormatted": format_duration(avg_duration),
            "byDomain": dict(sorted(by_domain.items(), key=lambda x: x[1], reverse=True)),
            "byMethod": dict(sorted(by_method.items(), key=lambda x: x[1], reverse=True)),
            "byStatusCode": dict(sorted(by_status.items(), key=lambda x: x[1], reverse=True)),
            "byResourceType": dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)),
        }

    def export_har(self) -> Dict[str, Any]:
        """
        导出HAR格式的网络日志

        Returns:
            HAR格式的字典
        """
        entries = []
        for req in self.requests:
            request_time_str = timestamp_to_datetime(req.request_time).isoformat() if req.request_time else ""

            entry = {
                "startedDateTime": request_time_str,
                "time": int(req.duration * 1000) if req.duration else 0,
                "request": {
                    "method": req.method,
                    "url": req.url,
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": k, "value": v}
                        for k, v in req.headers.items()
                    ],
                    "queryString": [],
                    "bodySize": len(req.post_data) if req.post_data else 0,
                    "postData": {
                        "mimeType": "application/x-www-form-urlencoded",
                        "text": req.post_data or "",
                    } if req.post_data else None,
                },
                "response": {
                    "status": req.status_code,
                    "statusText": req.status_text,
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": k, "value": v}
                        for k, v in req.response_headers.items()
                    ],
                    "content": {
                        "size": req.decoded_size,
                        "mimeType": req.response_headers.get("content-type", ""),
                    },
                    "bodySize": req.encoded_size,
                    "fromCache": req.from_cache,
                },
                "cache": {},
                "timings": {
                    "send": 0,
                    "wait": int(req.duration * 1000) if req.duration else 0,
                    "receive": 0,
                },
            }

            if req.failed:
                entry["_error"] = req.failure_reason

            entries.append(entry)

        har = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "DevToolsPilot-CLI",
                    "version": "0.1.0",
                },
                "entries": entries,
                "pages": [],
            }
        }

        return har

    def export_har_json(self, indent: int = 2) -> str:
        """
        导出HAR格式的JSON字符串

        Args:
            indent: JSON缩进

        Returns:
            HAR JSON字符串
        """
        return json.dumps(self.export_har(), indent=indent, ensure_ascii=False)

    def clear(self) -> None:
        """清除所有已记录的请求"""
        self.requests.clear()
        self._pending_requests.clear()

    def __repr__(self) -> str:
        return (
            f"NetworkMonitor(requests={len(self.requests)}, "
            f"recording={self._is_recording})"
        )
