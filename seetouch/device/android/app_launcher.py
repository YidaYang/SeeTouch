"""OPEN 动作:以应用名为一等公民的启动策略。

VLM 对应用名有可靠知识,对包名没有(2026-07-05 起,静态表/别名/包名直通
从 VLM 路径移除)。整体解析顺序:

  ① learned cache   之前学到的 (request -> package),持久化
  ② 索引精确匹配     应用显示名归一化后完全相等
  ③ 索引强模糊       唯一子串命中(如 "哔哩" -> "哔哩哔哩")直接启动
  ④ 候选反馈         多个/低置信候选 -> raise OpenAppNotFound(携带候选应用名),
                     由 Runner 反馈给模型重新输出精确名或关键词
  ⑤ package 直通     输入本身是 package 格式且已安装(内部调用兼容,VLM 不再输出包名)
  ⑥ 视觉兜底         索引不可用(PC 端无 applist.json)时回桌面 + raise OpenAppNeedsVisual

learned cache 写入时机:
  - 视觉兜底成功后由 Runner 调 learn_from_visual()
  - 强模糊命中且 verify_launch 确认前台后自动回写(已验证的映射,下次免搜索)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Callable

from ..base import OpenAppNeedsVisual, OpenAppNotFound
from .app_index import AppIndex, AppIndexSource


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
    """封装 OPEN 动作的应用名解析 + 启动流程。"""

    def __init__(
        self,
        installed_packages_getter: Callable[[], list[str]],
        start_app: Callable[[str], None],
        go_home: Callable[[], None],
        verify_launch: Callable[[str], bool] | None = None,
        index_source: AppIndexSource | None = None,
    ):
        """
        Args:
            installed_packages_getter: 返回设备已安装包名列表(learned/包名直通校验用)
            start_app:                 启动指定 package(通常是 device.app_start)
            go_home:                   回桌面(通常是 device.press("home"))
            verify_launch:             启动后验证当前前台是否就是该 package。None 时跳过验证
            index_source:              应用索引数据源(显示名 -> package)。None 时索引级跳过,
                                       未命中直接走视觉兜底
        """
        self._get_installed = installed_packages_getter
        self._start_app = start_app
        self._go_home = go_home
        self._verify = verify_launch
        self._index = AppIndex(index_source) if index_source is not None else None
        self._learned = _load_learned()

    def open(self, name_or_package: str) -> str:
        """启动 app,返回实际使用的 package。

        Raises:
            OpenAppNotFound:    索引可用但未高置信命中(携带候选应用名)
            OpenAppNeedsVisual: 索引不可用且其他途径都未命中(已回桌面)
        """
        request = (name_or_package or "").strip()
        if not request:
            raise OpenAppNeedsVisual(request)

        installed = self._get_installed_packages()

        # ① learned cache
        learned = self._learned.get(request)
        if learned and (not installed or learned in installed):
            if self._try_launch("learned", request, learned):
                return learned

        # ②③ 应用索引:精确 / 唯一强模糊
        candidates = []
        if self._index is not None and not self._index.is_empty():
            entry, candidates = self._index.resolve(request)
            if entry is not None:
                if self._try_launch("index", request, entry.package):
                    if entry.label != request:
                        # 强模糊命中且前台已验证,回写映射,下次免搜索
                        self.learn(request, entry.package, source="index-fuzzy")
                    return entry.package

        # ⑤ package 直通(内部调用兼容)
        if is_package_like(request) and request in installed:
            if self._try_launch("package", request, request):
                return request

        if self._index is not None and not self._index.is_empty():
            # ④ 候选反馈给模型
            suggestions = [c.entry.label for c in candidates]
            logger.info("[OPEN][not-found] %r suggestions=%s", request, suggestions)
            raise OpenAppNotFound(request, suggestions)

        # ⑥ 视觉兜底(无索引可用)
        logger.info("[OPEN][visual] %r -> go_home and signal runner", request)
        try:
            self._go_home()
        except Exception as exc:
            logger.warning("go_home before visual fallback failed: %s", exc)
        raise OpenAppNeedsVisual(request)

    def learn_from_visual(self, request: str, package: str) -> None:
        """视觉兜底成功后回写 learned cache。Runner 在前台变化时调用。"""
        self.learn(request, package, source="visual")

    def learn(self, request: str, package: str, source: str = "manual") -> None:
        """把已验证的 (request -> package) 映射写入持久化缓存。"""
        if not request or not package:
            return
        if self._learned.get(request) == package:
            return
        logger.info("[OPEN][learn] %r -> %s (from %s)", request, package, source)
        self._learned[request] = package
        _save_learned(self._learned)

    def _try_launch(self, tag: str, request: str, package: str) -> bool:
        logger.info("[OPEN][%s] %r -> %s (verifying...)", tag, request, package)
        try:
            self._start_app(package)
        except Exception as exc:
            logger.warning("start_app(%s) failed: %s", package, exc)
            return False
        if self._verify is None or self._verify(package):
            logger.info("[OPEN][%s] confirmed %s", tag, package)
            return True
        logger.info("[OPEN][%s] launch verify failed for %s", tag, package)
        return False

    def _get_installed_packages(self) -> list[str]:
        try:
            return list(self._get_installed())
        except Exception as exc:
            logger.warning("get installed packages failed: %s", exc)
            return []
