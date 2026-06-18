"""OPEN 动作的分级 fallback。

不维护"全量"映射表。整体策略:

  ① learned cache  之前视觉兜底学到的 (request -> package),持久化
  ② L1 静态表      高频中文名 -> package(一次性硬编码)
  ③ L1' alias      海外/旧版 package -> 国内替代(硬编码)
  ④ L2 直通        输入本身是 package 格式且已安装
  ⑤ L4 视觉兜底    回桌面 + raise OpenAppNeedsVisual,交给 Runner

注意:
- **不做模糊匹配**(2026-05-21 起移除)。原因:Android 包名公共部分太多,
  fuzzy 假阳性高,曾经把 com.zhiliaoapp.musically 误匹配到 com.biquge.ebook.app。
- **learned cache 只在视觉兜底成功后写入**,不在 L1/L2/L3 启动后自动写。
  原因:L1/L2 已经有静态权威映射,不需要学;视觉兜底学到的才是真正"模型 + 用户"
  共同验证过的新映射。

成功后由 Runner 通过 learn_from_visual() 写入 ~/.seetouch/learned_apps.json。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Callable

from . import app_table
from ..base import OpenAppNeedsVisual


logger = logging.getLogger(__name__)


# 学习缓存路径
LEARNED_CACHE_PATH = Path.home() / ".seetouch" / "learned_apps.json"

# package name 检测正则:至少两段,字符限制为 ASCII 字母数字下划线
_PACKAGE_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z0-9_]+)+$")


def is_package_like(s: str) -> bool:
    """启发式判断输入是否像 Android package name。"""
    return bool(_PACKAGE_PATTERN.match((s or "").strip()))


def _load_learned() -> dict[str, str]:
    if not LEARNED_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(LEARNED_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("read learned cache failed: %s", exc)
        return {}


def _save_learned(cache: dict[str, str]) -> None:
    try:
        LEARNED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEARNED_CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("save learned cache failed: %s", exc)


class AppLauncher:
    """封装 OPEN 动作的分级 fallback 流程。

    learned cache 只通过 learn_from_visual() 写入,不在普通启动路径自动学。
    """

    def __init__(
        self,
        installed_packages_getter: Callable[[], list[str]],
        start_app: Callable[[str], None],
        go_home: Callable[[], None],
        verify_launch: Callable[[str], bool] | None = None,
    ):
        """
        Args:
            installed_packages_getter: 返回设备已安装包名列表(通常是 device.app_list)
            start_app:                 启动指定 package(通常是 device.app_start)
            go_home:                   回桌面(通常是 device.press("home"))
            verify_launch:             启动后验证当前前台是否就是该 package。None 时跳过验证
        """
        self._get_installed = installed_packages_getter
        self._start_app = start_app
        self._go_home = go_home
        self._verify = verify_launch
        self._learned = _load_learned()

    def open(self, name_or_package: str) -> str:
        """启动 app。命中即启动并返回实际使用的 package;否则 raise OpenAppNeedsVisual。"""
        request = (name_or_package or "").strip()
        if not request:
            raise OpenAppNeedsVisual(request)

        installed = self._get_installed_packages()

        # 候选列表:learned -> 静态表 -> 海外别名 -> package 直通
        # 没有模糊匹配。每个候选 start + verify;成功直接返回,失败试下一个。
        candidates: list[tuple[str, str]] = []  # (source_tag, package)

        learned = self._learned.get(request)
        if learned and learned in installed:
            candidates.append(("learned", learned))

        l1 = app_table.lookup(request)
        if l1 and l1 in installed and l1 != learned:
            candidates.append(("L1 table", l1))

        alias = app_table.alias_for_package(request)
        if alias and alias in installed and alias not in (learned, l1):
            candidates.append(("L1 alias", alias))

        if is_package_like(request) and request in installed:
            if request not in (learned, l1, alias):
                candidates.append(("L2 direct", request))

        for tag, pkg in candidates:
            logger.info("[OPEN][%s] %r -> %s (verifying...)", tag, request, pkg)
            try:
                self._start_app(pkg)
            except Exception as exc:
                logger.warning("start_app(%s) failed: %s", pkg, exc)
                continue
            if self._verify is None or self._verify(pkg):
                logger.info("[OPEN][%s] confirmed %s", tag, pkg)
                return pkg
            logger.info("[OPEN][%s] launch verify failed for %s, trying next candidate", tag, pkg)

        # L4: 视觉兜底
        logger.info("[OPEN][L4 visual] %r -> go_home and signal runner", request)
        try:
            self._go_home()
        except Exception as exc:
            logger.warning("go_home before visual fallback failed: %s", exc)
        raise OpenAppNeedsVisual(request)

    def learn_from_visual(self, request: str, package: str) -> None:
        """视觉兜底成功后回写 learned cache。Runner 在前台变化时调用。"""
        if not request or not package:
            return
        if self._learned.get(request) == package:
            return
        logger.info("[OPEN][learn] %r -> %s (from visual fallback)", request, package)
        self._learned[request] = package
        _save_learned(self._learned)

    def _get_installed_packages(self) -> list[str]:
        try:
            return list(self._get_installed())
        except Exception as exc:
            logger.warning("get installed packages failed: %s", exc)
            return []
