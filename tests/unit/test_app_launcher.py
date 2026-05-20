"""app_launcher 单测。

不依赖真实 uiautomator2 / 真实手机;通过函数注入模拟 device 行为。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phone_agent.device.android.app_launcher import (
    AppLauncher,
    fuzzy_match,
    is_package_like,
)
from phone_agent.device.base import OpenAppNeedsVisual


# ---------- 纯函数测试 ----------

def test_is_package_like_positive():
    assert is_package_like("tv.danmaku.bili")
    assert is_package_like("com.taobao.taobao")
    assert is_package_like("a.b")


def test_is_package_like_negative():
    assert not is_package_like("哔哩哔哩")
    assert not is_package_like("bilibili")
    assert not is_package_like(".tv.bili")
    assert not is_package_like("")


def test_fuzzy_match_substring():
    candidates = ["tv.danmaku.bili", "com.taobao.taobao", "com.tencent.mm"]
    assert fuzzy_match("bili", candidates) == "tv.danmaku.bili"


def test_fuzzy_match_no_hit_returns_none():
    candidates = ["com.unrelated.foo", "com.unrelated.bar"]
    assert fuzzy_match("xxxxxxx", candidates) is None


def test_fuzzy_match_last_segment():
    candidates = ["com.taobao.taobao", "com.taobao.trip"]
    assert fuzzy_match("trip", candidates) == "com.taobao.trip"


# ---------- AppLauncher 集成 ----------

@pytest.fixture
def launched(tmp_path, monkeypatch):
    """每个测试用临时 home 目录避免污染真实 learned cache。"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # 重新导入以重置 module-level LEARNED_CACHE_PATH
    import importlib

    from phone_agent.device.android import app_launcher
    importlib.reload(app_launcher)

    started: list[str] = []
    home_called: list[bool] = []

    installed = ["tv.danmaku.bili", "com.taobao.taobao", "com.foo.bar"]

    launcher = app_launcher.AppLauncher(
        installed_packages_getter=lambda: installed,
        start_app=lambda pkg: started.append(pkg),
        go_home=lambda: home_called.append(True),
    )
    return launcher, started, home_called, installed, app_launcher


def test_l1_static_table_hit(launched):
    launcher, started, home, _, _ = launched
    pkg = launcher.open("哔哩哔哩")
    assert pkg == "tv.danmaku.bili"
    assert started == ["tv.danmaku.bili"]
    assert home == []


def test_l2_package_direct(launched):
    launcher, started, home, _, _ = launched
    pkg = launcher.open("com.foo.bar")
    assert pkg == "com.foo.bar"
    assert started == ["com.foo.bar"]


def test_l3_fuzzy_match(launched):
    launcher, started, home, _, _ = launched
    pkg = launcher.open("taobao")
    assert pkg == "com.taobao.taobao"
    assert started == ["com.taobao.taobao"]


def test_l4_visual_fallback_raises_and_goes_home(launched):
    launcher, started, home, _, _ = launched
    with pytest.raises(OpenAppNeedsVisual):
        launcher.open("某个完全不存在的应用xxxyyy")
    assert started == []
    assert home == [True]


def test_learned_cache_persists(launched):
    launcher, _, _, installed, app_launcher_module = launched
    launcher.open("哔哩哔哩")
    cache_path = app_launcher_module.LEARNED_CACHE_PATH
    assert cache_path.exists()
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["哔哩哔哩"] == "tv.danmaku.bili"
