"""DeviceController 抽象接口 + 共用异常。"""

from __future__ import annotations

from typing import Protocol, Tuple, runtime_checkable

from PIL import Image


class DeviceError(Exception):
    """设备层通用异常。"""


class OpenAppFailed(DeviceError):
    """OPEN 动作完全失败(L1-L4 都没成功)。"""


class OpenAppNeedsVisual(DeviceError):
    """L1-L3 都未命中,需要由 Reasoner 通过视觉在桌面找图标。

    设备已经回到桌面,Runner 应记录一笔 note,让下一次循环交给 Reasoner 处理。
    """

    def __init__(self, requested: str):
        super().__init__(f"app launcher fallback to visual: {requested!r}")
        self.requested = requested


@runtime_checkable
class DeviceController(Protocol):
    """跨平台设备控制抽象。

    所有坐标接口都使用归一化坐标 [0, 1000];实现内部负责到像素的换算。
    """

    def screenshot(self) -> Image.Image:
        """获取当前屏幕截图(PIL Image)。"""
        ...

    def screen_size(self) -> Tuple[int, int]:
        """返回设备像素尺寸 (width, height)。"""
        ...

    def click(self, x_norm: int, y_norm: int) -> None:
        """单击。坐标范围 [0, 1000]。"""
        ...

    def type_text(self, text: str) -> None:
        """在当前焦点输入框输入文本(支持中文)。"""
        ...

    def scroll(
        self,
        start_norm: Tuple[int, int],
        end_norm: Tuple[int, int],
    ) -> None:
        """从 start 滑到 end,坐标归一化。"""
        ...

    def open_app(self, name_or_package: str) -> None:
        """启动 app。可接受中文名或 Android package name。

        实现应按 L1->L4 fallback 处理,L3 失败时 raise OpenAppNeedsVisual。
        """
        ...

    def go_home(self) -> None:
        """回到桌面。"""
        ...
