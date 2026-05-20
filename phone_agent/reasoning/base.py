"""推理层的抽象接口与共享数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from PIL import Image

from ..core.action import Action, ActionOutput


@dataclass
class StepRecord:
    """Runner 在 history 里给 Reasoner 的每步上下文。"""

    step: int
    action: Action
    screen_summary: str = ""
    action_summary: str = ""
    execution_success: bool | None = None
    raw_output: str = ""
    notes: list[str] = field(default_factory=list)


@runtime_checkable
class Reasoner(Protocol):
    """根据当前截图 + 用户任务 + 历史,输出下一步动作。"""

    def predict(
        self,
        instruction: str,
        screenshot: Image.Image,
        history: list[StepRecord],
    ) -> ActionOutput:
        ...


__all__ = ["Reasoner", "StepRecord", "Action", "ActionOutput"]
