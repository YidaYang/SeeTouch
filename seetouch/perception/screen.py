"""感知:坐标归一化 <-> 像素 转换,以及图像编码工具。

模型与 Action 都使用 0-1000 归一化坐标;设备控制层接收的是像素坐标。
本模块负责无损转换。
"""

from __future__ import annotations

import base64
import io
from typing import Tuple

from PIL import Image


NORM_MAX = 1000


def norm_to_pixel(
    x_norm: int | float,
    y_norm: int | float,
    screen_size: Tuple[int, int],
) -> Tuple[int, int]:
    """归一化坐标 [0,1000] -> 像素坐标。

    Args:
        x_norm, y_norm: 归一化坐标
        screen_size:    设备像素尺寸 (width, height)

    Returns:
        (x_pixel, y_pixel)
    """
    width, height = screen_size
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid screen_size: {screen_size}")

    x_pixel = round(_clip_norm(x_norm) / NORM_MAX * width)
    y_pixel = round(_clip_norm(y_norm) / NORM_MAX * height)
    # 限制到屏幕内,避免点到边界外
    x_pixel = max(0, min(width - 1, x_pixel))
    y_pixel = max(0, min(height - 1, y_pixel))
    return x_pixel, y_pixel


def pixel_to_norm(
    x_pixel: int | float,
    y_pixel: int | float,
    screen_size: Tuple[int, int],
) -> Tuple[int, int]:
    """像素坐标 -> 归一化坐标 [0,1000]。"""
    width, height = screen_size
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid screen_size: {screen_size}")

    x_norm = round(float(x_pixel) / width * NORM_MAX)
    y_norm = round(float(y_pixel) / height * NORM_MAX)
    return _clip_norm(x_norm), _clip_norm(y_norm)


def _clip_norm(value: int | float) -> int:
    return int(max(0, min(NORM_MAX, round(float(value)))))


def encode_image_data_url(image: Image.Image, image_format: str = "PNG") -> str:
    """把 PIL Image 编码成 data URL,供多模态 chat API 使用。"""
    buf = io.BytesIO()
    image.save(buf, format=image_format)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/{image_format.lower()};base64,{b64}"
