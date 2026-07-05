"""应用索引:应用显示名 -> package 的查找与模糊搜索。

VLM 只有"应用名"知识,没有可靠的包名知识,所以 OPEN 以应用名为一等公民:
索引提供 精确匹配 / 模糊搜索,由 AppLauncher 决定启动或把候选反馈给模型。

索引源(AppIndexSource)是可插拔抽象:
  - on-device: DeviceBridge 走 PackageManager 枚举桌面可启动应用
  - PC 端:    读取 helper APK 导出的 applist.json(scripts/pull_applist.py)
  - 测试:     StaticAppIndexSource 直接注入条目

模糊匹配策略(顺序即置信度):
  1. 归一化后完全相等(casefold + 去空白/常见分隔符)
  2. 一方包含另一方(子串),按长度占比打分
  3. difflib SequenceMatcher 相似度
只有归一化相等视为"精确";子串/相似度命中只作为候选反馈,
除非唯一且为强子串命中(见 AppIndex.resolve)。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable


logger = logging.getLogger(__name__)

# 归一化时去掉的字符:空白 + 常见分隔/装饰符号
_STRIP_PATTERN = re.compile(r"[\s\-_·•.。,，:：()（）\[\]【】]+")

# 模糊候选的最低相似度(经验值:低于此值的候选对模型没有参考价值)
_MIN_SCORE = 0.45


def normalize_label(s: str) -> str:
    """应用名归一化:casefold + 去空白与常见分隔符。"""
    return _STRIP_PATTERN.sub("", (s or "")).casefold()


@dataclass(frozen=True)
class AppIndexEntry:
    """索引中的一条应用记录。"""

    label: str
    package: str


@dataclass(frozen=True)
class ScoredEntry:
    """带相似度得分的搜索结果。"""

    entry: AppIndexEntry
    score: float
    substring: bool  # 是否为子串命中(强于纯相似度)


@runtime_checkable
class AppIndexSource(Protocol):
    """索引数据源抽象。"""

    def entries(self) -> list[AppIndexEntry]:
        """返回当前设备全部可启动应用。实现自行决定缓存策略。"""
        ...


class StaticAppIndexSource:
    """固定条目数据源(测试 / 内存注入)。"""

    def __init__(self, entries: Iterable[AppIndexEntry]):
        self._entries = list(entries)

    def entries(self) -> list[AppIndexEntry]:
        return list(self._entries)


class AppListJsonSource:
    """从 helper APK 导出的 applist.json 读取索引(PC 端)。

    默认路径 ~/.seetouch/applist.json,可用环境变量 SEETOUCH_APPLIST_PATH 覆盖。
    文件缺失/损坏时返回空列表(上层自动退化为视觉兜底)。
    """

    def __init__(self, path: str | Path | None = None):
        import os

        if path is None:
            path = os.environ.get("SEETOUCH_APPLIST_PATH") or (
                Path.home() / ".seetouch" / "applist.json"
            )
        self._path = Path(path)
        self._cache: list[AppIndexEntry] | None = None

    def entries(self) -> list[AppIndexEntry]:
        if self._cache is not None:
            return self._cache
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._cache = [
                AppIndexEntry(label=str(app["label"]), package=str(app["package"]))
                for app in data.get("apps", [])
                if app.get("label") and app.get("package")
            ]
            logger.info("applist.json loaded: %d apps from %s", len(self._cache), self._path)
        except FileNotFoundError:
            logger.info("applist.json not found at %s (index disabled)", self._path)
            self._cache = []
        except Exception as exc:
            logger.warning("applist.json parse failed (%s): %s", self._path, exc)
            self._cache = []
        return self._cache


class AppIndex:
    """应用索引查询门面:精确匹配 + 模糊搜索。"""

    def __init__(self, source: AppIndexSource):
        self._source = source

    def is_empty(self) -> bool:
        return not self._entries()

    def exact(self, name: str) -> AppIndexEntry | None:
        """归一化后完全相等的匹配。多个同名时返回第一个。"""
        wanted = normalize_label(name)
        if not wanted:
            return None
        for entry in self._entries():
            if normalize_label(entry.label) == wanted:
                return entry
        return None

    def search(self, query: str, limit: int = 6) -> list[ScoredEntry]:
        """模糊搜索,按相似度降序返回至多 limit 个候选。"""
        wanted = normalize_label(query)
        if not wanted:
            return []
        scored: list[ScoredEntry] = []
        for entry in self._entries():
            label = normalize_label(entry.label)
            if not label:
                continue
            if wanted == label:
                scored.append(ScoredEntry(entry, 1.0, True))
            elif wanted in label or label in wanted:
                shorter, longer = sorted((wanted, label), key=len)
                scored.append(ScoredEntry(entry, 0.6 + 0.35 * len(shorter) / len(longer), True))
            else:
                ratio = SequenceMatcher(None, wanted, label).ratio()
                if ratio >= _MIN_SCORE:
                    scored.append(ScoredEntry(entry, ratio, False))
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:limit]

    def resolve(self, query: str) -> tuple[AppIndexEntry | None, list[ScoredEntry]]:
        """一次性解析:返回 (可直接启动的高置信条目, 候选列表)。

        高置信 = 归一化精确匹配,或唯一的子串命中。
        其余情况返回 (None, candidates),由上层把候选反馈给模型。
        """
        entry = self.exact(query)
        if entry is not None:
            return entry, []
        candidates = self.search(query)
        substrings = [c for c in candidates if c.substring]
        if len(substrings) == 1:
            return substrings[0].entry, candidates
        return None, candidates

    def _entries(self) -> list[AppIndexEntry]:
        try:
            return self._source.entries()
        except Exception as exc:
            logger.warning("app index source failed: %s", exc)
            return []
