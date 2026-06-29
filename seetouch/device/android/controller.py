"""AndroidController: uiautomator2 实现 DeviceController 接口。

调用前需要先 `python -m uiautomator2 init` 在手机上装好 atx-agent。
"""

from __future__ import annotations

import logging
import time
from typing import Tuple

from PIL import Image

from ..base import DeviceError
from ...perception.screen import norm_to_pixel
from .app_launcher import AppLauncher


logger = logging.getLogger(__name__)


class AndroidController:
    """uiautomator2 驱动的 Android DeviceController 实现。"""

    def __init__(self, serial: str | None = None):
        """
        Args:
            serial: 设备 serial number;None 时自动选择(单设备场景)
        """
        try:
            import uiautomator2 as u2  # 延迟导入,避免无设备环境也能 import 这个模块
        except ImportError as exc:
            raise DeviceError(
                "uiautomator2 not installed. run: pip install uiautomator2"
            ) from exc

        try:
            self._d = u2.connect(serial) if serial else u2.connect()
        except Exception as exc:
            raise DeviceError(f"connect to android device failed: {exc}") from exc

        self._screen_size: Tuple[int, int] | None = None
        self._launcher = AppLauncher(
            installed_packages_getter=self._safe_app_list,
            start_app=self._d.app_start,
            go_home=lambda: self._d.press("home"),
            verify_launch=self._verify_launch,
        )

    def _verify_launch(self, package: str, timeout: float = 3.0) -> bool:
        """轮询 app_current(),确认指定 package 已经在前台。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            current = self.current_app()
            if current == package:
                return True
            time.sleep(0.3)
        logger.info("verify_launch(%s) timeout; current=%s", package, self.current_app())
        return False

    # ------------------------- DeviceController API -------------------------

    def screenshot(self) -> Image.Image:
        img = self._d.screenshot()
        # u2 的 screenshot() 在新版本返回 PIL Image,旧版本可能返回 numpy
        if not isinstance(img, Image.Image):
            img = Image.fromarray(img)
        return img

    def screen_size(self) -> Tuple[int, int]:
        if self._screen_size is None:
            w, h = self._d.window_size()
            self._screen_size = (int(w), int(h))
        return self._screen_size

    def click(self, x_norm: int, y_norm: int) -> None:
        x, y = norm_to_pixel(x_norm, y_norm, self.screen_size())
        logger.debug("click norm=(%s,%s) px=(%s,%s)", x_norm, y_norm, x, y)
        self._d.click(x, y)

    def type_text(self, text: str) -> None:
        # u2 在焦点输入框上 set_text 原生支持中文(走 atx-agent 调 UiAutomator)
        if not text:
            return
        try:
            # 先尝试当前焦点字段
            self._d(focused=True).set_text(text)
        except Exception as exc:
            logger.warning("set_text on focused field failed: %s; fallback to send_keys", exc)
            try:
                self._d.send_keys(text)
            except Exception as exc2:
                raise DeviceError(f"type_text failed: {exc2}") from exc2

    def scroll(
        self,
        start_norm: Tuple[int, int],
        end_norm: Tuple[int, int],
    ) -> None:
        size = self.screen_size()
        fx, fy = norm_to_pixel(start_norm[0], start_norm[1], size)
        tx, ty = norm_to_pixel(end_norm[0], end_norm[1], size)
        logger.debug("scroll (%s,%s)->(%s,%s) px (%s,%s)->(%s,%s)",
                     start_norm[0], start_norm[1], end_norm[0], end_norm[1], fx, fy, tx, ty)
        self._d.swipe(fx, fy, tx, ty, duration=0.4)

    def open_app(self, name_or_package: str) -> None:
        """通过 AppLauncher 走四级 fallback;L4 时 raise OpenAppNeedsVisual。"""
        self._launcher.open(name_or_package)

    def go_home(self) -> None:
        self._d.press("home")

    def back(self) -> None:
        self._d.press("back")

    def current_app(self) -> str | None:
        """当前前台 app 的 package(用于 Runner 判断启动是否成功 / 视觉兜底是否捕获新 app)。"""
        try:
            info = self._d.app_current()
            return info.get("package")
        except Exception:
            return None

    def learn_app_from_visual(self, request: str, package: str) -> None:
        """转给 AppLauncher 写入 learned cache。"""
        self._launcher.learn_from_visual(request, package)

    # ------------------------- 内部 helpers -------------------------

    def _safe_app_list(self) -> list[str]:
        try:
            return list(self._d.app_list())
        except Exception as exc:
            logger.warning("app_list failed: %s", exc)
            return []
