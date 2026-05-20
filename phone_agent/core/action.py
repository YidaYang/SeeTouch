"""标准动作定义,与比赛动作协议对齐。

所有坐标都是 0-1000 的归一化坐标,设备控制层负责到像素的换算。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ActionType = Literal["CLICK", "TYPE", "SCROLL", "OPEN", "COMPLETE"]


ACTION_CLICK: ActionType = "CLICK"
ACTION_TYPE: ActionType = "TYPE"
ACTION_SCROLL: ActionType = "SCROLL"
ACTION_OPEN: ActionType = "OPEN"
ACTION_COMPLETE: ActionType = "COMPLETE"

VALID_ACTIONS: frozenset[str] = frozenset(
    {ACTION_CLICK, ACTION_TYPE, ACTION_SCROLL, ACTION_OPEN, ACTION_COMPLETE}
)


@dataclass
class Action:
    """一个标准动作。

    parameters 形状(归一化坐标 0-1000):
        CLICK:    {"point": [x, y]}
        TYPE:     {"text": "..."}
        SCROLL:   {"start_point": [x, y], "end_point": [x, y]}
        OPEN:     {"app_name": "..."}    # 中文名 或 Android package
        COMPLETE: {}
    """

    type: ActionType
    parameters: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.type not in VALID_ACTIONS:
            raise ValueError(f"Invalid action type: {self.type!r}")

        if self.type == ACTION_CLICK:
            point = self.parameters.get("point")
            if not (isinstance(point, (list, tuple)) and len(point) == 2):
                raise ValueError(f"CLICK requires parameters.point [x,y], got {point!r}")
        elif self.type == ACTION_TYPE:
            if not isinstance(self.parameters.get("text"), str):
                raise ValueError("TYPE requires parameters.text (str)")
        elif self.type == ACTION_SCROLL:
            for key in ("start_point", "end_point"):
                pt = self.parameters.get(key)
                if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                    raise ValueError(f"SCROLL requires parameters.{key} [x,y]")
        elif self.type == ACTION_OPEN:
            if not isinstance(self.parameters.get("app_name"), str):
                raise ValueError("OPEN requires parameters.app_name (str)")
        # COMPLETE: no params required


@dataclass
class ActionOutput:
    """Reasoner 一次预测的完整输出。

    Attributes:
        action:         解析后的标准动作
        raw_output:     模型原始文本,用于调试和回放
        screen_summary: 模型对当前截图的描述
        action_summary: 模型对本步动作的解释
        usage:          token 使用统计(可选)
    """

    action: Action
    raw_output: str = ""
    screen_summary: str = ""
    action_summary: str = ""
    usage: dict[str, Any] | None = None
