"""发布-订阅事件总线。

为 Runner / DebugSession / 日志桥接 等模块提供松耦合的事件通信。
线程安全:emit 可在工作线程调用,handler 在 emit 所在线程同步执行。

典型事件:
    step.screenshot_taken  — 截图 + 降分辨率完成
    step.reasoning_started — 开始调用 VLM API
    step.reasoning_done    — VLM 返回,parse 完成
    step.executing         — 开始执行设备动作
    step.completed         — 单步全部完成
    log                    — 日志记录(由 LogBridge 发射)
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

# 事件类型常量
STEP_SCREENSHOT_TAKEN = "step.screenshot_taken"
STEP_REASONING_STARTED = "step.reasoning_started"
STEP_REASONING_DONE = "step.reasoning_done"
STEP_EXECUTING = "step.executing"
STEP_COMPLETED = "step.completed"
LOG = "log"

# 处理器签名: Callable[..., None],接受 emit 时传入的关键字参数
EventHandler = Callable[..., Any]


class EventBus:
    """发布-订阅事件总线。

    用法::

        bus = EventBus()
        bus.subscribe("step.screenshot_taken", my_handler)
        bus.emit("step.screenshot_taken", step=1, screenshot=img)

    特性:
    - 同一事件可挂多个处理器,按注册顺序执行
    - handler 抛异常不影响后续 handler
    - 线程安全(用 RLock 保护订阅列表)
    - emit 在调用线程同步执行 handler
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """注册事件处理器。同一 handler 可重复注册(会多次调用)。"""
        with self._lock:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """移除事件处理器。未注册的 handler 会静默忽略。"""
        with self._lock:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    def emit(self, event_type: str, **data: Any) -> None:
        """发射事件,同步调用所有已注册的处理器。

        Args:
            event_type: 事件类型字符串
            **data: 传递给处理器的关键字参数
        """
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
        for handler in handlers:
            try:
                handler(**data)
            except Exception:
                logger.exception(
                    "event handler %r failed for event %r",
                    handler, event_type,
                )

    def clear(self) -> None:
        """移除所有事件处理器。"""
        with self._lock:
            self._handlers.clear()
