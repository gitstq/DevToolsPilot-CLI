"""
截图引擎模块

通过CDP Page域实现页面截图功能：
- 全页面截图
- 元素截图
- 视口截图
- PNG格式保存
- Base64编码输出
- 自定义截图参数（质量、格式、裁剪）
"""

import base64
import logging
import os
from typing import Any, Dict, Optional, Tuple

from .cdp_client import CDPClient, CDPError
from .config import Config
from .utils import ensure_dir, generate_filename, save_base64_to_file, timestamp_ms

logger = logging.getLogger(__name__)


class ScreenshotEngine:
    """
    截图引擎

    通过CDP Page.captureScreenshot命令实现页面截图。

    Attributes:
        client: CDP客户端实例
        output_dir: 截图保存目录

    Example:
        >>> engine = ScreenshotEngine(client, output_dir="./screenshots")
        >>> filepath = await engine.capture_full_page()
        >>> base64_data = await engine.capture_viewport(return_base64=True)
    """

    def __init__(
        self,
        client: CDPClient,
        output_dir: str = "./screenshots",
    ):
        """
        初始化截图引擎

        Args:
            client: CDP客户端实例
            output_dir: 截图保存目录
        """
        self.client = client
        self.output_dir = output_dir

    async def capture_viewport(
        self,
        format: str = "png",
        quality: int = 80,
        clip: Optional[Dict[str, float]] = None,
        from_surface: bool = True,
        optimize_for_speed: bool = False,
        return_base64: bool = False,
        filepath: Optional[str] = None,
    ) -> Optional[str]:
        """
        截取当前视口

        Args:
            format: 图片格式 ("png" 或 "jpeg")
            quality: JPEG质量 (0-100)
            clip: 裁剪区域 {"x": float, "y": float, "width": float, "height": float, "scale": float}
            from_surface: 是否从表面捕获
            optimize_for_speed: 是否优化速度
            return_base64: 是否返回Base64编码而非保存文件
            filepath: 自定义保存路径

        Returns:
            保存的文件路径或Base64字符串，失败返回None
        """
        params: Dict[str, Any] = {
            "format": format,
            "quality": quality,
            "fromSurface": from_surface,
            "optimizeForSpeed": optimize_for_speed,
        }

        if clip:
            params["clip"] = clip

        try:
            result = await self.client.send("Page.captureScreenshot", params)
            base64_data = result.get("data", "")

            if not base64_data:
                logger.error("截图返回空数据")
                return None

            if return_base64:
                return base64_data

            # 保存到文件
            if filepath is None:
                filepath = os.path.join(
                    self.output_dir,
                    generate_filename("viewport", format),
                )

            return save_base64_to_file(base64_data, filepath)

        except CDPError as e:
            logger.error(f"截图失败: {e}")
            return None

    async def capture_full_page(
        self,
        format: str = "png",
        quality: int = 80,
        filepath: Optional[str] = None,
        return_base64: bool = False,
    ) -> Optional[str]:
        """
        截取完整页面（包括滚动区域外的内容）

        通过获取页面完整尺寸，调整视口大小后截图实现。

        Args:
            format: 图片格式
            quality: JPEG质量
            filepath: 自定义保存路径
            return_base64: 是否返回Base64

        Returns:
            文件路径或Base64字符串
        """
        try:
            # 获取页面布局信息
            layout_result = await self.client.send(
                "Page.getLayoutMetrics"
            )

            # 获取内容尺寸
            css_content_size = layout_result.get("cssContentSize", {})
            width = css_content_size.get("width", 0)
            height = css_content_size.get("height", 0)

            if width <= 0 or height <= 0:
                # 回退到视口截图
                logger.warning("无法获取页面尺寸，回退到视口截图")
                return await self.capture_viewport(
                    format=format,
                    quality=quality,
                    filepath=filepath,
                    return_base64=return_base64,
                )

            # 获取当前设备度量
            emulated_result = await self.client.send(
                "Emulation.getDeviceMetricsOverride"
            )
            original_metrics = emulated_result if emulated_result else None

            # 设置模拟视口为完整页面大小
            await self.client.send("Emulation.setDeviceMetricsOverride", {
                "width": int(width),
                "height": int(height),
                "deviceScaleFactor": 1,
                "mobile": False,
            })

            # 截图
            result = await self.capture_viewport(
                format=format,
                quality=quality,
                filepath=filepath,
                return_base64=return_base64,
            )

            # 恢复原始视口
            if original_metrics:
                try:
                    await self.client.send(
                        "Emulation.setDeviceMetricsOverride",
                        original_metrics,
                    )
                except CDPError:
                    pass
            else:
                try:
                    await self.client.send("Emulation.clearDeviceMetricsOverride")
                except CDPError:
                    pass

            return result

        except CDPError as e:
            logger.error(f"全页面截图失败: {e}")
            # 回退到视口截图
            return await self.capture_viewport(
                format=format,
                quality=quality,
                filepath=filepath,
                return_base64=return_base64,
            )

    async def capture_element(
        self,
        selector: str,
        format: str = "png",
        quality: int = 80,
        padding: int = 0,
        filepath: Optional[str] = None,
        return_base64: bool = False,
    ) -> Optional[str]:
        """
        截取指定元素

        Args:
            selector: CSS选择器
            format: 图片格式
            quality: JPEG质量
            padding: 元素周围的额外边距（像素）
            filepath: 自定义保存路径
            return_base64: 是否返回Base64

        Returns:
            文件路径或Base64字符串
        """
        try:
            # 获取元素的位置和大小
            box_result = await self.client.send(
                "Runtime.evaluate",
                {
                    "expression": (
                        f"(function() {{"
                        f"  const el = document.querySelector({selector!r});"
                        f"  if (!el) return null;"
                        f"  const rect = el.getBoundingClientRect();"
                        f"  return {{"
                        f"    x: rect.x, y: rect.y,"
                        f"    width: rect.width, height: rect.height"
                        f"  }};"
                        f"}})()"
                    ),
                    "returnByValue": True,
                },
            )

            box = box_result.get("result", {}).get("value")
            if not box or not isinstance(box, dict):
                logger.error(f"未找到元素: {selector}")
                return None

            # 获取设备像素比
            device_pixel_ratio = 1
            try:
                dpr_result = await self.client.send(
                    "Runtime.evaluate",
                    {"expression": "window.devicePixelRatio || 1", "returnByValue": True},
                )
                device_pixel_ratio = dpr_result.get("result", {}).get("value", 1)
            except CDPError:
                pass

            # 构建裁剪区域
            clip = {
                "x": max(0, box["x"] - padding) * device_pixel_ratio,
                "y": max(0, box["y"] - padding) * device_pixel_ratio,
                "width": (box["width"] + padding * 2) * device_pixel_ratio,
                "height": (box["height"] + padding * 2) * device_pixel_ratio,
                "scale": device_pixel_ratio,
            }

            return await self.capture_viewport(
                format=format,
                quality=quality,
                clip=clip,
                filepath=filepath,
                return_base64=return_base64,
            )

        except CDPError as e:
            logger.error(f"元素截图失败: {e}")
            return None

    async def capture_to_bytes(
        self,
        format: str = "png",
        quality: int = 80,
    ) -> Optional[bytes]:
        """
        截取视口并返回原始字节

        Args:
            format: 图片格式
            quality: JPEG质量

        Returns:
            图片字节数据
        """
        base64_data = await self.capture_viewport(
            format=format,
            quality=quality,
            return_base64=True,
        )

        if base64_data:
            return base64.b64decode(base64_data)
        return None

    def __repr__(self) -> str:
        return f"ScreenshotEngine(output_dir={self.output_dir!r})"
