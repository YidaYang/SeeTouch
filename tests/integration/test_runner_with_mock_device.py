"""Runner 集成测试:用 MockDevice + MockReasoner 跑一个完整的多步任务。"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from phone_agent.core.action import (
    ACTION_CLICK,
    ACTION_COMPLETE,
    ACTION_OPEN,
    ACTION_SCROLL,
    ACTION_TYPE,
    Action,
    ActionOutput,
)
from phone_agent.core.runner import Runner
from phone_agent.core.task import Task
from phone_agent.device.base import OpenAppNeedsVisual
from phone_agent.safety.guard import Guard


class MockDevice:
    def __init__(self, screen_size=(1080, 2400)):
        self._size = screen_size
        self.actions: list[tuple[str, tuple]] = []
        self._current_app: str | None = None
        self.learned: list[tuple[str, str]] = []

    def screenshot(self) -> Image.Image:
        return Image.new("RGB", self._size, (255, 255, 255))

    def screen_size(self):
        return self._size

    def click(self, x, y):
        self.actions.append(("click", (x, y)))

    def type_text(self, text):
        self.actions.append(("type", (text,)))

    def scroll(self, start, end):
        self.actions.append(("scroll", (start, end)))

    def open_app(self, name):
        self.actions.append(("open", (name,)))

    def go_home(self):
        self.actions.append(("home", ()))

    def current_app(self) -> str | None:
        return self._current_app

    def learn_app_from_visual(self, request: str, package: str) -> None:
        self.learned.append((request, package))


class MockReasoner:
    def __init__(self, scripted_outputs: list[ActionOutput]):
        self._outputs = list(scripted_outputs)
        self.calls = 0

    def predict(self, instruction, screenshot, history):
        self.calls += 1
        if self._outputs:
            return self._outputs.pop(0)
        return ActionOutput(action=Action(type=ACTION_COMPLETE, parameters={}))


def _make_outputs() -> list[ActionOutput]:
    return [
        ActionOutput(
            action=Action(type=ACTION_OPEN, parameters={"app_name": "哔哩哔哩"}),
            screen_summary="桌面",
            action_summary="启动哔哩哔哩",
        ),
        ActionOutput(
            action=Action(type=ACTION_CLICK, parameters={"point": [500, 100]}),
            screen_summary="B 站首页",
            action_summary="点击搜索",
        ),
        ActionOutput(
            action=Action(type=ACTION_TYPE, parameters={"text": "采莲曲"}),
            screen_summary="搜索框激活",
            action_summary="输入关键词",
        ),
        ActionOutput(
            action=Action(type=ACTION_COMPLETE, parameters={}),
            screen_summary="搜索结果页",
            action_summary="任务完成",
        ),
    ]


def test_runner_completes_normal_task(tmp_path: Path):
    device = MockDevice()
    reasoner = MockReasoner(_make_outputs())
    runner = Runner(
        device=device,
        reasoner=reasoner,
        guard=Guard(prompt_fn=lambda _msg: False),  # 不会被触发(任务非敏感)
        runs_dir=tmp_path,
    )

    result = runner.run(Task(instruction="在哔哩哔哩搜索采莲曲"))

    assert result.completed
    assert result.aborted_reason is None
    assert result.total_steps == 4
    assert reasoner.calls == 4

    # 设备实际被调用的动作
    types = [a[0] for a in device.actions]
    assert types == ["open", "click", "type"]

    # trace.jsonl 文件应该存在并有 4 行
    trace_path = Path(result.runs_dir) / "trace.jsonl"
    lines = [ln for ln in trace_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 4

    # summary.json 应该写入
    summary = json.loads((Path(result.runs_dir) / "summary.json").read_text(encoding="utf-8"))
    assert summary["completed"] is True


def test_runner_aborts_on_user_denial(tmp_path: Path):
    device = MockDevice()
    reasoner = MockReasoner([
        ActionOutput(
            action=Action(type=ACTION_CLICK, parameters={"point": [500, 800]}),
            screen_summary="结算页",
            action_summary="点击立即支付",
        ),
    ])
    runner = Runner(
        device=device,
        reasoner=reasoner,
        guard=Guard(prompt_fn=lambda _msg: False),
        runs_dir=tmp_path,
    )

    result = runner.run(Task(instruction="美团下单并支付一份外卖"))

    assert not result.completed
    assert result.aborted_reason == "user_denied"
    # 用户拒绝,设备不应被点击
    assert device.actions == []


def test_runner_handles_open_app_visual_fallback(tmp_path: Path):
    """OpenAppNeedsVisual 不应算失败,应继续 loop 让 reasoner 处理。
    点击图标后前台变化时,Runner 应触发 learn_app_from_visual 回写 cache。
    """

    class VisualFallbackDevice(MockDevice):
        def __init__(self):
            super().__init__()
            self._current_app = "com.miui.home"  # 初始在桌面
            self._click_count = 0

        def open_app(self, name):
            self.actions.append(("open", (name,)))
            raise OpenAppNeedsVisual(name)

        def click(self, x, y):
            super().click(x, y)
            # 模拟点击图标后前台变成目标 app
            self._click_count += 1
            if self._click_count == 1:
                self._current_app = "com.weird.unknown"

    device = VisualFallbackDevice()
    reasoner = MockReasoner([
        ActionOutput(
            action=Action(type=ACTION_OPEN, parameters={"app_name": "极冷门app"}),
            action_summary="启动极冷门app",
        ),
        ActionOutput(
            action=Action(type=ACTION_CLICK, parameters={"point": [200, 600]}),
            action_summary="点击桌面上的极冷门 app 图标",
        ),
        ActionOutput(
            action=Action(type=ACTION_COMPLETE, parameters={}),
            action_summary="完成",
        ),
    ])
    runner = Runner(
        device=device,
        reasoner=reasoner,
        guard=Guard(prompt_fn=lambda _msg: False),
        runs_dir=tmp_path,
    )

    result = runner.run(Task(instruction="打开极冷门app"))

    assert result.completed
    assert result.total_steps == 3
    types = [a[0] for a in device.actions]
    assert types == ["open", "click"]
    # 关键:视觉兜底成功后,Runner 应该把 (request -> 实际 package) 记下来
    assert device.learned == [("极冷门app", "com.weird.unknown")]


def test_runner_visual_fallback_with_swipe_pages(tmp_path: Path):
    """模型在桌面翻页找 app,SCROLL 不应触发 learn(因为前台还是桌面)。"""

    class VisualFallbackDevice(MockDevice):
        def __init__(self):
            super().__init__()
            self._current_app = "com.miui.home"

        def open_app(self, name):
            self.actions.append(("open", (name,)))
            raise OpenAppNeedsVisual(name)

        def scroll(self, start, end):
            super().scroll(start, end)
            # 翻页后还在桌面

        def click(self, x, y):
            super().click(x, y)
            self._current_app = "com.target.app"

    device = VisualFallbackDevice()
    reasoner = MockReasoner([
        ActionOutput(
            action=Action(type=ACTION_OPEN, parameters={"app_name": "目标app"}),
            action_summary="启动",
        ),
        ActionOutput(
            action=Action(type=ACTION_SCROLL, parameters={"start_point": [800, 500], "end_point": [200, 500]}),
            action_summary="向左翻页",
        ),
        ActionOutput(
            action=Action(type=ACTION_SCROLL, parameters={"start_point": [800, 500], "end_point": [200, 500]}),
            action_summary="再向左翻页",
        ),
        ActionOutput(
            action=Action(type=ACTION_CLICK, parameters={"point": [300, 700]}),
            action_summary="点击图标",
        ),
        ActionOutput(
            action=Action(type=ACTION_COMPLETE, parameters={}),
            action_summary="完成",
        ),
    ])
    runner = Runner(
        device=device,
        reasoner=reasoner,
        guard=Guard(prompt_fn=lambda _msg: False),
        runs_dir=tmp_path,
    )
    result = runner.run(Task(instruction="打开目标app"))

    assert result.completed
    # 翻页 2 次没切前台,只有点击图标后切换,才学一次
    assert device.learned == [("目标app", "com.target.app")]
