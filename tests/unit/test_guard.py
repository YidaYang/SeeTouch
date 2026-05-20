"""safety/guard.py 单测。"""

from __future__ import annotations

from phone_agent.core.action import (
    ACTION_CLICK,
    ACTION_COMPLETE,
    ACTION_OPEN,
    Action,
    ActionOutput,
)
from phone_agent.core.task import Task
from phone_agent.safety.guard import (
    Guard,
    action_is_sensitive,
    task_is_sensitive,
)


def _output(
    action_type: str = ACTION_CLICK,
    parameters: dict | None = None,
    action_summary: str = "",
    screen_summary: str = "",
) -> ActionOutput:
    return ActionOutput(
        action=Action(type=action_type, parameters=parameters or {"point": [100, 100]}),
        action_summary=action_summary,
        screen_summary=screen_summary,
    )


# ---------- 关键词识别 ----------

def test_task_sensitive_for_payment():
    assert task_is_sensitive("帮我在美团支付外卖订单")


def test_task_sensitive_for_order():
    assert task_is_sensitive("在饿了么下单一份麦当劳")


def test_task_not_sensitive_for_browse():
    assert not task_is_sensitive("打开抖音看看推荐视频")


def test_action_sensitive_for_pay_button():
    out = _output(action_summary="点击立即支付按钮")
    assert action_is_sensitive(out)


def test_action_not_sensitive_when_complete():
    out = _output(action_type=ACTION_COMPLETE, action_summary="任务完成")
    assert not action_is_sensitive(out)


def test_action_not_sensitive_for_browsing_click():
    out = _output(action_summary="点击搜索框")
    assert not action_is_sensitive(out)


# ---------- Guard 组合 ----------

def test_needs_confirmation_combines_task_and_action():
    task = Task(instruction="去美团下单一份猪蹄")
    sensitive_out = _output(action_summary="点击确认下单按钮")
    benign_out = _output(action_summary="点击搜索框")

    guard = Guard(prompt_fn=lambda _msg: True)
    assert guard.needs_confirmation(task, sensitive_out)
    assert not guard.needs_confirmation(task, benign_out)


def test_needs_confirmation_false_when_task_not_sensitive():
    task = Task(instruction="打开抖音")
    sensitive_out = _output(action_summary="点击立即支付")
    guard = Guard(prompt_fn=lambda _msg: True)
    assert not guard.needs_confirmation(task, sensitive_out)


def test_ask_uses_prompt_fn():
    answers = []
    def fake_prompt(message: str) -> bool:
        answers.append(message)
        return False

    guard = Guard(prompt_fn=fake_prompt)
    out = _output(action_summary="点击立即支付", screen_summary="支付页")
    approved = guard.ask(out, screenshot_path="/tmp/x.png")
    assert approved is False
    assert len(answers) == 1
    assert "立即支付" in answers[0]
    assert "/tmp/x.png" in answers[0]
