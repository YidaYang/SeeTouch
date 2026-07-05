"""app_launcher 单测(应用名优先策略)。

不依赖真实 uiautomator2 / 真实手机;通过函数注入模拟 device 行为,
应用索引用 StaticAppIndexSource 注入。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seetouch.device.android.app_index import AppIndexEntry, StaticAppIndexSource
from seetouch.device.android.app_launcher import is_package_like
from seetouch.device.base import OpenAppNeedsVisual, OpenAppNotFound


def test_is_package_like_positive():
    assert is_package_like("tv.danmaku.bili")
    assert is_package_like("com.taobao.taobao")
    assert is_package_like("a.b")


def test_is_package_like_negative():
    assert not is_package_like("哔哩哔哩")
    assert not is_package_like("bilibili")
    assert not is_package_like(".tv.bili")
    assert not is_package_like("")


INDEX_ENTRIES = [
    AppIndexEntry(label="哔哩哔哩", package="tv.danmaku.bili"),
    AppIndexEntry(label="淘宝", package="com.taobao.taobao"),
    AppIndexEntry(label="设置", package="com.android.settings"),
    AppIndexEntry(label="高德地图", package="com.autonavi.minimap"),
    AppIndexEntry(label="百度地图", package="com.baidu.BaiduMap"),
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    """每个测试用临时 home 目录避免污染真实 learned cache。"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    import importlib

    from seetouch.device.android import app_launcher
    importlib.reload(app_launcher)

    started: list[str] = []
    home_called: list[bool] = []
    installed = [e.package for e in INDEX_ENTRIES] + ["com.foo.bar"]

    def make(index_entries=INDEX_ENTRIES, with_index=True):
        return app_launcher.AppLauncher(
            installed_packages_getter=lambda: installed,
            start_app=lambda pkg: started.append(pkg),
            go_home=lambda: home_called.append(True),
            index_source=StaticAppIndexSource(index_entries) if with_index else None,
        )

    return make, started, home_called, installed, app_launcher


def test_exact_label_hit(env):
    """应用名精确命中:直接启动,不写 learned cache。"""
    make, started, home, _, mod = env
    launcher = make()
    assert launcher.open("哔哩哔哩") == "tv.danmaku.bili"
    assert started == ["tv.danmaku.bili"]
    assert home == []
    assert not mod.LEARNED_CACHE_PATH.exists()


def test_exact_label_hit_normalized(env):
    """归一化匹配:空格/大小写差异不影响命中。"""
    make, started, _, _, _ = env
    launcher = make([AppIndexEntry(label="Bilibili", package="tv.danmaku.bili")])
    assert launcher.open("bilibili") == "tv.danmaku.bili"
    assert started == ["tv.danmaku.bili"]


def test_unique_substring_launches_and_learns(env):
    """唯一子串命中(关键词):直接启动,并回写 learned cache。"""
    make, started, _, _, mod = env
    launcher = make()
    assert launcher.open("哔哩") == "tv.danmaku.bili"
    assert started == ["tv.danmaku.bili"]
    cache = json.loads(mod.LEARNED_CACHE_PATH.read_text(encoding="utf-8"))
    assert cache["哔哩"] == "tv.danmaku.bili"


def test_ambiguous_raises_not_found_with_suggestions(env):
    """多个子串候选(地图):不猜,携带候选反馈给模型。"""
    make, started, home, _, _ = env
    launcher = make()
    with pytest.raises(OpenAppNotFound) as exc_info:
        launcher.open("地图")
    assert started == []
    assert home == []  # 候选反馈不回桌面
    labels = exc_info.value.suggestions
    assert "高德地图" in labels and "百度地图" in labels


def test_no_match_raises_not_found_empty_suggestions(env):
    """完全不相关的名字:OpenAppNotFound 且候选为空。"""
    make, started, _, _, _ = env
    launcher = make()
    with pytest.raises(OpenAppNotFound) as exc_info:
        launcher.open("qqqzzzz不存在的应用wwww")
    assert started == []
    assert exc_info.value.suggestions == []


def test_package_direct_still_works(env):
    """package 直通保留(内部调用兼容),不经索引。"""
    make, started, _, _, _ = env
    launcher = make()
    assert launcher.open("com.foo.bar") == "com.foo.bar"
    assert started == ["com.foo.bar"]


def test_no_index_falls_back_to_visual(env):
    """无索引可用(PC 端无 applist.json):回桌面 + OpenAppNeedsVisual。"""
    make, started, home, _, _ = env
    launcher = make(with_index=False)
    with pytest.raises(OpenAppNeedsVisual):
        launcher.open("哔哩哔哩")
    assert started == []
    assert home == [True]


def test_empty_index_falls_back_to_visual(env):
    """索引源存在但为空(applist.json 缺失):同样走视觉兜底。"""
    make, started, home, _, _ = env
    launcher = make(index_entries=[])
    with pytest.raises(OpenAppNeedsVisual):
        launcher.open("哔哩哔哩")
    assert started == []
    assert home == [True]


def test_learn_from_visual_writes_cache(env):
    """视觉兜底成功后,Runner 会调用 learn_from_visual 回写 cache。"""
    make, _, _, _, mod = env
    launcher = make()
    launcher.learn_from_visual("超级冷门app", "com.weird.app")
    cache = json.loads(mod.LEARNED_CACHE_PATH.read_text(encoding="utf-8"))
    assert cache["超级冷门app"] == "com.weird.app"


def test_learned_cache_used_on_next_open(env):
    """learn 之后,下次 open 同样的请求,直接走 learned 路径。"""
    make, started, _, installed, _ = env
    launcher = make()
    installed.append("com.weird.app")
    launcher.learn_from_visual("超级冷门app", "com.weird.app")
    assert launcher.open("超级冷门app") == "com.weird.app"
    assert started == ["com.weird.app"]


def test_learn_from_visual_ignores_empty(env):
    """空 request 或空 package 不应写入 cache。"""
    make, _, _, _, mod = env
    launcher = make()
    launcher.learn_from_visual("", "com.x")
    launcher.learn_from_visual("x", "")
    assert not mod.LEARNED_CACHE_PATH.exists()


def test_exact_launch_does_not_auto_learn(env):
    """精确命中/包名直通启动成功不写 cache,只有强模糊与视觉兜底才写。"""
    make, _, _, _, mod = env
    launcher = make()
    launcher.open("哔哩哔哩")
    launcher.open("com.foo.bar")
    assert not mod.LEARNED_CACHE_PATH.exists()
