"""app_index 单测:归一化、精确匹配、模糊搜索、resolve、json 源。"""

from __future__ import annotations

import json

from seetouch.device.android.app_index import (
    AppIndex,
    AppIndexEntry,
    AppListJsonSource,
    StaticAppIndexSource,
    normalize_label,
)


ENTRIES = [
    AppIndexEntry(label="哔哩哔哩", package="tv.danmaku.bili"),
    AppIndexEntry(label="淘宝", package="com.taobao.taobao"),
    AppIndexEntry(label="高德地图", package="com.autonavi.minimap"),
    AppIndexEntry(label="百度地图", package="com.baidu.BaiduMap"),
    AppIndexEntry(label="QQ 音乐", package="com.tencent.qqmusic"),
]


def make_index(entries=ENTRIES) -> AppIndex:
    return AppIndex(StaticAppIndexSource(entries))


def test_normalize_label():
    assert normalize_label("QQ 音乐") == "qq音乐"
    assert normalize_label("Bili-Bili") == "bilibili"
    assert normalize_label("") == ""


def test_exact_match_normalized():
    index = make_index()
    entry = index.exact("qq音乐")
    assert entry is not None and entry.package == "com.tencent.qqmusic"
    assert index.exact("不存在") is None


def test_search_substring_ranked_first():
    index = make_index()
    results = index.search("地图")
    assert len(results) == 2
    assert all(r.substring for r in results)
    labels = {r.entry.label for r in results}
    assert labels == {"高德地图", "百度地图"}


def test_resolve_exact():
    entry, candidates = make_index().resolve("哔哩哔哩")
    assert entry is not None and entry.package == "tv.danmaku.bili"
    assert candidates == []


def test_resolve_unique_substring():
    entry, _ = make_index().resolve("哔哩")
    assert entry is not None and entry.package == "tv.danmaku.bili"


def test_resolve_ambiguous_returns_candidates():
    entry, candidates = make_index().resolve("地图")
    assert entry is None
    assert {c.entry.label for c in candidates} == {"高德地图", "百度地图"}


def test_resolve_no_match():
    entry, candidates = make_index().resolve("zzz毫无关系qqq")
    assert entry is None
    assert candidates == []


def test_applist_json_source(tmp_path):
    path = tmp_path / "applist.json"
    path.write_text(
        json.dumps({"apps": [{"label": "微信", "package": "com.tencent.mm"}]}),
        encoding="utf-8",
    )
    source = AppListJsonSource(path)
    assert source.entries() == [AppIndexEntry(label="微信", package="com.tencent.mm")]


def test_applist_json_source_missing_file(tmp_path):
    source = AppListJsonSource(tmp_path / "nope.json")
    assert source.entries() == []
    assert AppIndex(source).is_empty()
