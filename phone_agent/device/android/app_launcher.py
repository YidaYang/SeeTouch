"""OPEN 动作的四级 fallback。

不维护"全量"映射表。整体策略:

  L1 [静态表]      app_table.lookup() -> package         O(1)
  L2 [package 直通] 若输入是 package 格式且已安装 -> 启动
  L3 [模糊匹配]    在 device.app_list() 里做相似度匹配 -> 启动最高分
  L4 [视觉兜底]    回桌面 + raise OpenAppNeedsVisual,交给 Runner

成功后写入 learned cache(~/.phone_agent/learned_apps.json),下次秒开。
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from pathlib import Path
from typing import Callable, Iterable

from . import app_table
from ..base import OpenAppNeedsVisual


logger = logging.getLogger(__name__)


# 学习缓存路径
LEARNED_CACHE_PATH = Path.home() / ".phone_agent" / "learned_apps.json"

# 模糊匹配最低相似度阈值(收紧:之前 0.6 会把毫不相关的 com.xxx 包匹进来)
FUZZY_MIN_SCORE = 0.75

# 这些公共前缀在 Android 包名里到处都是,算相似度时先剥掉,避免假阳性
_COMMON_PACKAGE_PREFIXES = ("com.", "cn.", "org.", "net.", "io.", "tv.")

# 末尾段是这些通用词时,不参与短长度的子串匹配("app" / "android" / "main" 这类不能算特征)
_GENERIC_SEGMENTS = {
    "app", "android", "main", "mobile", "client", "pro", "lite", "free",
    "phone", "tv", "go", "plus", "x", "ui", "ui1", "ui2", "core",
}

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


def _strip_common_prefix(s: str) -> str:
    for prefix in _COMMON_PACKAGE_PREFIXES:
        if s.startswith(prefix):
            return s[len(prefix):]
    return s


def fuzzy_match(query: str, candidates: Iterable[str], min_score: float = FUZZY_MIN_SCORE) -> str | None:
    """对候选 package 列表做模糊匹配。返回最高分(>= min_score)或 None。

    匹配策略(取最高分,基于剥掉公共前缀后的核心部分):
      - 末尾段精确匹配(0.95)
      - 末尾段双向包含(0.85)
      - query 是 core 的子串(0.8)
      - 剥前缀后整体相似度(difflib)
    """
    q = (query or "").strip().lower()
    if not q:
        return None
    q_core = _strip_common_prefix(q)

    best: tuple[float, str] | None = None
    for cand in candidates:
        c = cand.lower()
        c_core = _strip_common_prefix(c)
        score = 0.0

        # 末尾段(如 "bili" vs "tv.danmaku.bili" 的 "bili")
        last_segment = c.rsplit(".", 1)[-1] if "." in c else c
        if last_segment == q_core:
            score = max(score, 0.95)
        elif (
            q_core
            and last_segment not in _GENERIC_SEGMENTS
            and (q_core in last_segment or last_segment in q_core)
            and min(len(q_core), len(last_segment)) >= 4
        ):
            score = max(score, 0.85)

        # 子串(query 在剥前缀的 candidate 里)
        if q_core and len(q_core) >= 4 and q_core in c_core:
            score = max(score, 0.8)

        # 整体相似度(剥前缀后再比,避免 "com." 这种公共部分稀释差异)
        ratio = difflib.SequenceMatcher(None, q_core, c_core).ratio()
        score = max(score, ratio)

        if score >= min_score and (best is None or score > best[0]):
            best = (score, cand)

    return best[1] if best else None


class AppLauncher:
    """封装 OPEN 动作的四级 fallback 流程。

    learned cache 只在 verify_launch 返回 True 后才写入(避免错匹配被固化)。
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
        """启动 app。命中即启动并返回实际使用的 package;否则 raise OpenAppNeedsVisual。

        Returns:
            实际启动的 package name
        """
        request = (name_or_package or "").strip()
        if not request:
            raise OpenAppNeedsVisual(request)

        installed = self._get_installed_packages()

        # 候选列表按优先级:learned -> 静态表 -> 海外别名 -> 自己 -> 模糊匹配
        # 每个候选都尝试 start + verify;成功才学,失败继续下一个
        candidates: list[tuple[str, str]] = []  # (source_tag, package)

        learned = self._learned.get(request)
        if learned and learned in installed:
            candidates.append(("learned", learned))

        l1 = app_table.lookup(request)
        if l1 and l1 in installed and l1 != learned:
            candidates.append(("L1 table", l1))

        # 模型可能给出海外/旧版包名;若对应的国内替代已安装,优先试它
        alias = app_table.alias_for_package(request)
        if alias and alias in installed and alias not in (learned, l1):
            candidates.append(("L1 alias", alias))

        if is_package_like(request) and request in installed:
            if request not in (learned, l1, alias):
                candidates.append(("L2 direct", request))

        match = fuzzy_match(request, installed)
        if match and match not in (learned, l1, alias, request):
            candidates.append(("L3 fuzzy", match))

        for tag, pkg in candidates:
            logger.info("[OPEN][%s] %r -> %s (verifying...)", tag, request, pkg)
            try:
                self._start_app(pkg)
            except Exception as exc:
                logger.warning("start_app(%s) failed: %s", pkg, exc)
                continue
            if self._verify is None or self._verify(pkg):
                logger.info("[OPEN][%s] confirmed %s", tag, pkg)
                self._learn(request, pkg)
                return pkg
            logger.info("[OPEN][%s] launch verify failed for %s, trying next candidate", tag, pkg)
            # 错误的 learned cache 在这里发现:撤销它
            if tag == "learned":
                self._unlearn(request)

        # L4: 视觉兜底
        logger.info("[OPEN][L4 visual] %r -> go_home and signal runner", request)
        try:
            self._go_home()
        except Exception as exc:
            logger.warning("go_home before visual fallback failed: %s", exc)
        raise OpenAppNeedsVisual(request)

    def _get_installed_packages(self) -> list[str]:
        try:
            return list(self._get_installed())
        except Exception as exc:
            logger.warning("get installed packages failed: %s", exc)
            return []

    def _learn(self, request: str, package: str) -> None:
        if not request or not package or self._learned.get(request) == package:
            return
        self._learned[request] = package
        _save_learned(self._learned)

    def _unlearn(self, request: str) -> None:
        if request in self._learned:
            self._learned.pop(request)
            _save_learned(self._learned)
