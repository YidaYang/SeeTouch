"""任务数据类。"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


def _default_task_id() -> str:
    return f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"


@dataclass
class Task:
    """一次自然语言任务。

    Attributes:
        instruction: 用户原始指令
        task_id:     任务唯一标识(用于 runs/<task_id>/ 目录)
        max_steps:   单任务最大步数,默认 45(与比赛一致)
    """

    instruction: str
    task_id: str = field(default_factory=_default_task_id)
    max_steps: int = 45
