"""app_launcher 单测。

不依赖真实 uiautomator2 / 真实手机;通过函数注入模拟 device 行为。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phone_agent.device.android.app_launcher import (
    AppLauncher,
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
    """L1 静态表命中:启动成功,但因为没有视觉兜底参与,不写 cache。"""
    launcher, started, home, _, app_launcher_module = launched
    pkg = launcher.open("哔哩哔哩")
    assert pkg == "tv.danmaku.bili"
    assert started == ["tv.danmaku.bili"]
    assert home == []
    # cache 不应被写入(只有视觉兜底才学)
    assert not app_launcher_module.LEARNED_CACHE_PATH.exists()


def test_l1_alias_overseas_to_domestic(launched):
    """模型给海外 package 时,alias 表能找到国内替代。"""
    launcher, started, home, installed, _ = launched
    installed.append("com.ss.android.ugc.aweme")
    pkg = launcher.open("com.zhiliaoapp.musically")
    assert pkg == "com.ss.android.ugc.aweme"


def test_l2_package_direct(launched):
    launcher, started, _, _, _ = launched
    pkg = launcher.open("com.foo.bar")
    assert pkg == "com.foo.bar"
    assert started == ["com.foo.bar"]


def test_unknown_app_raises_visual_fallback(launched):
    """L1/L2/alias 都未命中时,直接 raise OpenAppNeedsVisual + go_home。"""
    launcher, started, home, _, _ = launched
    with pytest.raises(OpenAppNeedsVisual):
        launcher.open("某个完全不存在的应用xxxyyy")
    assert started == []
    assert home == [True]


def test_no_fuzzy_match_anymore(launched):
    """关键回归:模糊匹配已删除,不应再把不相关的 com.xxx 误匹配。

    历史 bug:com.zhiliaoapp.musically 曾经被 fuzzy 误配到 com.biquge.ebook.app。
    """
    launcher, started, home, installed, _ = launched
    installed.append("com.biquge.ebook.app")
    with pytest.raises(OpenAppNeedsVisual):
        launcher.open("com.zhiliaoapp.musically")  # 不在 installed 里、也没 alias 命中(alias 默认指向抖音)
    assert "com.biquge.ebook.app" not in started


def test_learn_from_visual_writes_cache(launched):
    """视觉兜底成功后,Runner 会调用 learn_from_visual 回写 cache。"""
    launcher, _, _, _, app_launcher_module = launched
    launcher.learn_from_visual("超级冷门app", "com.weird.app")
    cache = json.loads(app_launcher_module.LEARNED_CACHE_PATH.read_text(encoding="utf-8"))
    assert cache["超级冷门app"] == "com.weird.app"


def test_learned_cache_used_on_next_open(launched):
    """learn 之后,下次 open 同样的请求,直接走 learned 路径(只要 package 已安装)。"""
    launcher, started, _, installed, _ = launched
    installed.append("com.weird.app")
    launcher.learn_from_visual("超级冷门app", "com.weird.app")
    pkg = launcher.open("超级冷门app")
    assert pkg == "com.weird.app"
    assert started == ["com.weird.app"]


def test_learn_from_visual_ignores_empty(launched):
    """空 request 或空 package 不应写入 cache。"""
    launcher, _, _, _, app_launcher_module = launched
    launcher.learn_from_visual("", "com.x")
    launcher.learn_from_visual("x", "")
    assert not app_launcher_module.LEARNED_CACHE_PATH.exists()
