"""敏感动作识别与用户确认。

判定逻辑(均满足才拦截):
  1. 任务指令含敏感关键词(支付/下单/发送/删除/订车/提交 等)
  2. 当前动作的语义指向"确认类操作"(点击支付/确认下单/发送/删除按钮 等)
  3. action 类型不是 COMPLETE(任务结束本身安全)

命中后调用 prompt_fn 让用户确认,默认 CLI input;返回 True 才放行。
"""

from __future__ import annotations

import logging
from typing import Callable

from ..core.action import ACTION_COMPLETE, ActionOutput
from ..core.task import Task


logger = logging.getLogger(__name__)


# 任务级敏感关键词:出现在 user instruction 时进入"敏感模式"
SENSITIVE_TASK_KEYWORDS: tuple[str, ...] = (
    "支付", "付款", "结账", "下单", "买", "购买", "订",
    "提交", "确认", "签到打卡",
    "发送", "发布", "发表", "发消息", "发评论",
    "删除", "清除",
    "转账", "转钱", "提现",
    "登录", "注册",
)

# 动作级敏感关键词:出现在 action_summary 或 screen_summary 表明这一步要敲下"确认/支付"键
SENSITIVE_ACTION_KEYWORDS: tuple[str, ...] = (
    "支付", "付款", "立即支付", "确认支付",
    "下单", "确认下单", "立即下单", "提交订单",
    "确认", "确定",
    "提交", "立即购买",
    "发送", "发布", "发表",
    "删除", "确认删除",
    "立即叫车", "确认叫车", "呼叫",
    "转账", "提现",
)


def task_is_sensitive(instruction: str) -> bool:
    text = (instruction or "").strip()
    if not text:
        return False
    return any(kw in text for kw in SENSITIVE_TASK_KEYWORDS)


def action_is_sensitive(out: ActionOutput) -> bool:
    if out.action.type == ACTION_COMPLETE:
        return False
    haystack = " ".join([out.action_summary or "", out.screen_summary or ""])
    if not haystack.strip():
        return False
    return any(kw in haystack for kw in SENSITIVE_ACTION_KEYWORDS)


def _default_cli_prompt(message: str) -> bool:
    """默认 CLI 询问:任何非空且以 y/Y 开头的回答视为同意,其它(含空)视为拒绝。"""
    try:
        answer = input(message).strip()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.lower().startswith("y")


class Guard:
    """组合 task-level 和 action-level 判断,负责拦截+提示。"""

    def __init__(self, prompt_fn: Callable[[str], bool] | None = None):
        self._prompt = prompt_fn or _default_cli_prompt

    def needs_confirmation(self, task: Task, out: ActionOutput) -> bool:
        if not task_is_sensitive(task.instruction):
            return False
        return action_is_sensitive(out)

    def ask(self, out: ActionOutput, *, screenshot_path: str | None = None) -> bool:
        """向用户呈现动作并询问是否放行。同意返回 True。"""
        params_str = ", ".join(f"{k}={v}" for k, v in out.action.parameters.items())
        lines = [
            "",
            "============== 敏感动作待确认 ==============",
            f"动作类型:{out.action.type}",
            f"参数:    {params_str}",
        ]
        if out.action_summary:
            lines.append(f"操作描述:{out.action_summary}")
        if out.screen_summary:
            lines.append(f"界面状态:{out.screen_summary}")
        if screenshot_path:
            lines.append(f"截图路径:{screenshot_path}")
        lines.append("继续执行?[y/N]: ")
        message = "\n".join(lines)
        approved = self._prompt(message)
        logger.info("guard.ask -> %s", "approved" if approved else "denied")
        return approved
