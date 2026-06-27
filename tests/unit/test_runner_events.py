"""Runner 事件发射测试:验证 Runner 在各阶段正确触发 EventBus 事件。"""

from unittest.mock import MagicMock, patch
from PIL import Image

from seetouch.core.action import ACTION_CLICK, ACTION_COMPLETE, Action, ActionOutput
from seetouch.core.event_bus import (
    EventBus,
    STEP_SCREENSHOT_TAKEN,
    STEP_REASONING_STARTED,
    STEP_REASONING_DONE,
    STEP_EXECUTING,
)
from seetouch.core.runner import Runner
from seetouch.core.task import Task


def _make_runner_with_events(action_sequence: list[ActionOutput]):
    """构造带 EventBus 的 Runner(mock device + reasoner)。"""
    device = MagicMock()
    device.screenshot.return_value = Image.new("RGB", (720, 1600), (128, 128, 128))
    device.current_app.return_value = "com.test.app"
    device.screen_size.return_value = (1080, 2400)

    call_count = {"n": 0}

    def mock_predict(instruction, screenshot, history):
        idx = min(call_count["n"], len(action_sequence) - 1)
        call_count["n"] += 1
        return action_sequence[idx]

    reasoner = MagicMock()
    reasoner.predict = mock_predict

    bus = EventBus()
    runner = Runner(
        device=device,
        reasoner=reasoner,
        runs_dir="runs",
        event_bus=bus,
    )
    return runner, bus, device


def test_runner_emits_events_in_order():
    """step() 应按顺序发射: screenshot_taken -> reasoning_started -> reasoning_done -> executing。"""
    out = ActionOutput(
        action=Action(type=ACTION_CLICK, parameters={"point": [500, 500]}),
        raw_output='{"action":"CLICK","parameters":{"point":[500,500]}}',
        screen_summary="test",
        action_summary="click",
        prompt_text="test prompt",
    )
    complete = ActionOutput(
        action=Action(type=ACTION_COMPLETE, parameters={}),
        raw_output='{"action":"COMPLETE","parameters":{}}',
        screen_summary="done",
        action_summary="complete",
        prompt_text="test prompt",
    )

    runner, bus, device = _make_runner_with_events([out, complete])

    events = []
    bus.subscribe(STEP_SCREENSHOT_TAKEN, lambda **kw: events.append(("screenshot_taken", kw.get("step"))))
    bus.subscribe(STEP_REASONING_STARTED, lambda **kw: events.append(("reasoning_started", kw.get("step"))))
    bus.subscribe(STEP_REASONING_DONE, lambda **kw: events.append(("reasoning_done", kw.get("step"))))
    bus.subscribe(STEP_EXECUTING, lambda **kw: events.append(("executing", kw.get("step"))))

    task = Task(instruction="test", max_steps=5)
    runner.start(task)
    result = runner.step()

    assert not result.terminal
    # 验证事件顺序
    event_types = [e[0] for e in events]
    assert event_types == [
        "screenshot_taken",
        "reasoning_started",
        "reasoning_done",
        "executing",
    ]
    # 验证 step 编号
    assert all(e[1] == 1 for e in events)


def test_runner_emits_screenshot_with_image():
    """screenshot_taken 事件应包含 PIL Image。"""
    out = ActionOutput(
        action=Action(type=ACTION_COMPLETE, parameters={}),
        raw_output='{"action":"COMPLETE","parameters":{}}',
        screen_summary="done",
        action_summary="done",
        prompt_text="test",
    )
    runner, bus, device = _make_runner_with_events([out])

    received = {}
    bus.subscribe(STEP_SCREENSHOT_TAKEN, lambda **kw: received.update(kw))

    task = Task(instruction="test", max_steps=5)
    runner.start(task)
    runner.step()

    assert "screenshot" in received
    assert isinstance(received["screenshot"], Image.Image)


def test_runner_reasoning_done_includes_action():
    """reasoning_done 事件应包含 action 和 reasoning_time。"""
    out = ActionOutput(
        action=Action(type=ACTION_CLICK, parameters={"point": [100, 200]}),
        raw_output='{"action":"CLICK","parameters":{"point":[100,200]}}',
        screen_summary="test",
        action_summary="click",
        prompt_text="test",
    )
    complete = ActionOutput(
        action=Action(type=ACTION_COMPLETE, parameters={}),
        raw_output='{"action":"COMPLETE","parameters":{}}',
        screen_summary="done",
        action_summary="done",
        prompt_text="test",
    )
    runner, bus, device = _make_runner_with_events([out, complete])

    received = {}
    bus.subscribe(STEP_REASONING_DONE, lambda **kw: received.update(kw))

    task = Task(instruction="test", max_steps=5)
    runner.start(task)
    runner.step()

    assert received["action"].type == ACTION_CLICK
    assert "reasoning_time" in received
    assert isinstance(received["reasoning_time"], float)


def test_runner_no_events_without_bus():
    """不传 event_bus 时,Runner 不报错、正常工作。"""
    device = MagicMock()
    device.screenshot.return_value = Image.new("RGB", (720, 1600), (128, 128, 128))
    device.current_app.return_value = "com.test.app"
    device.screen_size.return_value = (1080, 2400)

    out = ActionOutput(
        action=Action(type=ACTION_COMPLETE, parameters={}),
        raw_output='{"action":"COMPLETE","parameters":{}}',
        screen_summary="done",
        action_summary="done",
        prompt_text="test",
    )
    reasoner = MagicMock()
    reasoner.predict.return_value = out

    # 不传 event_bus
    runner = Runner(device=device, reasoner=reasoner, runs_dir="runs")

    task = Task(instruction="test", max_steps=5)
    runner.start(task)
    result = runner.step()

    assert result.terminal
    assert result.terminal_reason == "completed"


def test_complete_action_does_not_emit_executing():
    """COMPLETE 动作不需要执行,不应 emit step.executing。"""
    out = ActionOutput(
        action=Action(type=ACTION_COMPLETE, parameters={}),
        raw_output='{"action":"COMPLETE","parameters":{}}',
        screen_summary="done",
        action_summary="done",
        prompt_text="test",
    )
    runner, bus, device = _make_runner_with_events([out])

    executing_called = []
    bus.subscribe(STEP_EXECUTING, lambda **kw: executing_called.append(True))

    task = Task(instruction="test", max_steps=5)
    runner.start(task)
    runner.step()

    assert len(executing_called) == 0
