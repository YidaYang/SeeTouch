"""调试会话管理:Runner 生命周期 + 线程协调。

DebugSession 在工作线程中执行 Runner.step()(涉及 device I/O 和 API 调用),
SocketIO 事件在主线程中处理。用 threading.Event 做阻塞/唤醒控制。
"""

from __future__ import annotations

import base64
import io
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Literal

from PIL import Image

from ..core.event_bus import (
    EventBus,
    LOG,
    STEP_EXECUTING,
    STEP_REASONING_DONE,
    STEP_REASONING_STARTED,
    STEP_SCREENSHOT_TAKEN,
)
from ..core.log_bridge import LogBridge
from ..core.runner import Runner
from ..core.session import StepResult
from ..core.task import Task


logger = logging.getLogger(__name__)


# 前端可消费的序列化步骤数据
@dataclass
class StepData:
    """StepResult 的可序列化版本,用于 WebSocket 推送。"""

    step: int
    screenshot_b64: str
    screenshot_path: str
    prompt_text: str
    raw_output: str
    reasoning_content: str
    action_type: str
    action_params: dict[str, Any]
    screen_summary: str
    action_summary: str
    execution_success: bool | None
    notes: list[str]
    usage: dict[str, Any] | None
    reasoning_time: float
    execution_time: float
    terminal: bool
    terminal_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "screenshot_b64": self.screenshot_b64,
            "screenshot_path": self.screenshot_path,
            "prompt_text": self.prompt_text,
            "raw_output": self.raw_output,
            "reasoning_content": self.reasoning_content,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "screen_summary": self.screen_summary,
            "action_summary": self.action_summary,
            "execution_success": self.execution_success,
            "notes": self.notes,
            "usage": self.usage,
            "reasoning_time": round(self.reasoning_time, 2),
            "execution_time": round(self.execution_time, 2),
            "terminal": self.terminal,
            "terminal_reason": self.terminal_reason,
        }


def _image_to_b64(img: Image.Image, max_width: int = 720) -> str:
    """将 PIL Image 压缩编码为 base64 JPEG,用于前端显示。"""
    # 缩小以节省传输带宽
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def step_result_to_data(result: StepResult) -> StepData:
    """将 StepResult 转换为可序列化的 StepData。"""
    return StepData(
        step=result.step,
        screenshot_b64=_image_to_b64(result.screenshot),
        screenshot_path=str(result.screenshot_path) if result.screenshot_path else "",
        prompt_text=result.prompt_text,
        raw_output=result.raw_output,
        reasoning_content=result.reasoning_content,
        action_type=result.action.type,
        action_params=result.action.parameters,
        screen_summary=result.screen_summary,
        action_summary=result.action_summary,
        execution_success=result.execution_success,
        notes=result.notes,
        usage=result.usage,
        reasoning_time=result.reasoning_time,
        execution_time=result.execution_time,
        terminal=result.terminal,
        terminal_reason=result.terminal_reason,
    )


SessionState = Literal["idle", "stepping", "running", "paused", "finished"]


class DebugSession:
    """管理一次调试会话。

    线程模型:
      - SocketIO 事件处理在主线程(Flask 线程)
      - Runner.step() 在工作线程(_worker)执行
      - 用 _step_event 和 _pause_event 做同步

    状态转换:
      idle -> stepping/running (start)
      stepping -> idle (step 完成后等待下一个 step 指令)
      running -> paused (pause) / finished (任务结束)
      paused -> stepping/running (resume)
      any -> idle (stop)
    """

    def __init__(self, runner: Runner, event_bus: EventBus | None = None):
        self.runner = runner
        self._state: SessionState = "idle"
        self._step_history: list[StepData] = []

        # 事件总线 + 日志桥接
        self._event_bus = event_bus
        self._log_bridge: LogBridge | None = None

        # 工作线程
        self._worker_thread: threading.Thread | None = None

        # 同步原语
        self._step_event = threading.Event()   # 通知工作线程执行下一步
        self._stop_event = threading.Event()   # 通知工作线程终止
        self._lock = threading.Lock()

        # 回调:由 app.py 设置,用于推送结果到前端
        self.on_step_result: Any = None   # Callable[[StepData], None]
        self.on_task_finished: Any = None  # Callable[[dict], None]
        self.on_error: Any = None         # Callable[[str], None]
        self.on_state_change: Any = None  # Callable[[SessionState], None]
        self.on_step_progress: Any = None  # Callable[[dict], None]
        self.on_log: Any = None           # Callable[[dict], None]

        # 订阅 EventBus 事件
        if self._event_bus:
            self._event_bus.subscribe(STEP_SCREENSHOT_TAKEN, self._on_screenshot_taken)
            self._event_bus.subscribe(STEP_REASONING_STARTED, self._on_reasoning_started)
            self._event_bus.subscribe(STEP_REASONING_DONE, self._on_reasoning_done)
            self._event_bus.subscribe(STEP_EXECUTING, self._on_executing)
            self._event_bus.subscribe(LOG, self._dispatch_log)


    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def step_history(self) -> list[StepData]:
        return list(self._step_history)

    def start_task(self, instruction: str, max_steps: int = 45) -> None:
        """开始新任务,在工作线程中运行。"""
        with self._lock:
            if self._state not in ("idle", "finished"):
                raise RuntimeError(f"cannot start: current state is {self._state}")

            self._step_history.clear()
            self._stop_event.clear()
            self._step_event.clear()

            task = Task(instruction=instruction, max_steps=max_steps)
            self.runner.start(task)

            # 安装日志桥接
            if self._event_bus:
                self._log_bridge = LogBridge(self._event_bus)
                self._log_bridge.install()

            self._state = "paused"  # 等待用户点 step 或 run
            self._worker_thread = threading.Thread(
                target=self._worker, daemon=True, name="debug-worker",
            )
            self._worker_thread.start()

    def do_step(self) -> None:
        """执行一步后暂停。"""
        with self._lock:
            if self._state not in ("paused",):
                raise RuntimeError(f"cannot step: current state is {self._state}")
            self._state = "stepping"
        self._step_event.set()

    def do_run(self) -> None:
        """连续执行直到暂停或结束。"""
        with self._lock:
            if self._state not in ("paused",):
                raise RuntimeError(f"cannot run: current state is {self._state}")
            self._state = "running"
        self._step_event.set()

    def do_pause(self) -> None:
        """暂停连续执行(当前步执行完后生效)。"""
        with self._lock:
            if self._state == "running":
                self._state = "paused"

    def do_stop(self) -> None:
        """终止任务。"""
        with self._lock:
            self._stop_event.set()
            self._step_event.set()  # 唤醒可能在等待的工作线程
        # 卸载日志桥接
        if self._log_bridge:
            self._log_bridge.uninstall()
            self._log_bridge = None

    def _set_state(self, new_state: SessionState) -> None:
        """更新状态并通知前端(调用方不应持有 _lock)。

        worker 线程的状态变更必须经由此方法推送,否则前端无从得知
        stepping->paused 这类后台转换,会导致按钮永久卡死。
        """
        with self._lock:
            self._state = new_state
        if self.on_state_change:
            try:
                self.on_state_change(new_state)
            except Exception:
                logger.exception("on_state_change callback failed")

    def _worker(self) -> None:
        """工作线程主循环。"""
        try:
            while True:
                # 等待指令(step/run)
                self._step_event.wait()
                self._step_event.clear()

                # 检查是否要停止
                if self._stop_event.is_set():
                    break

                # 执行步骤循环
                while True:
                    if self._stop_event.is_set():
                        break

                    # 执行一步
                    try:
                        result = self.runner.step()
                    except Exception as exc:
                        logger.exception("runner.step() failed")
                        if self.on_error:
                            self.on_error(f"执行出错: {type(exc).__name__}: {exc}")
                        self._set_state("finished")
                        return

                    step_data = step_result_to_data(result)
                    self._step_history.append(step_data)

                    # 推送结果
                    if self.on_step_result:
                        self.on_step_result(step_data)

                    # 任务结束
                    if result.terminal:
                        self._set_state("finished")
                        if self.on_task_finished:
                            session = self.runner.session
                            summary = session.summarize() if session else None
                            self.on_task_finished({
                                "completed": summary.completed if summary else False,
                                "aborted_reason": summary.aborted_reason if summary else None,
                                "total_steps": summary.total_steps if summary else 0,
                                "total_input_tokens": summary.total_input_tokens if summary else 0,
                                "total_output_tokens": summary.total_output_tokens if summary else 0,
                                "runs_dir": summary.runs_dir if summary else "",
                            })
                        return

                    # 单步(stepping)或被 do_pause() 打断(paused):执行完本步后暂停,
                    # 回到外层 wait 等待下一条指令。running 状态则继续循环。
                    with self._lock:
                        current = self._state
                    if current in ("stepping", "paused"):
                        self._set_state("paused")
                        break

        except Exception as exc:
            logger.exception("debug worker unexpected error")
            if self.on_error:
                self.on_error(f"工作线程异常: {type(exc).__name__}: {exc}")
        finally:
            # 卸载日志桥接
            if self._log_bridge:
                self._log_bridge.uninstall()
                self._log_bridge = None
            with self._lock:
                already_finished = self._state == "finished"
            if not already_finished:
                self._set_state("finished" if self.runner.is_finished else "idle")

    # ======================== EventBus 事件处理 ========================

    def _on_screenshot_taken(self, step: int, screenshot: Any, **_kw: Any) -> None:
        """截图完成:立即推送截图到前端。"""
        if self.on_step_progress:
            self.on_step_progress({
                "phase": "screenshot_taken",
                "step": step,
                "screenshot_b64": _image_to_b64(screenshot),
            })

    def _on_reasoning_started(self, step: int, **_kw: Any) -> None:
        """推理开始:通知前端显示思考动画。"""
        if self.on_step_progress:
            self.on_step_progress({
                "phase": "reasoning_started",
                "step": step,
            })

    def _on_reasoning_done(
        self, step: int, action: Any, reasoning_time: float, **_kw: Any,
    ) -> None:
        """推理完成:通知前端隐藏思考动画、画动作标注。"""
        if self.on_step_progress:
            self.on_step_progress({
                "phase": "reasoning_done",
                "step": step,
                "action_type": action.type,
                "action_params": action.parameters,
                "reasoning_time": round(reasoning_time, 2),
            })

    def _on_executing(self, step: int, action: Any, **_kw: Any) -> None:
        """执行开始:通知前端。"""
        if self.on_step_progress:
            self.on_step_progress({
                "phase": "executing",
                "step": step,
                "action_type": action.type,
                "action_params": action.parameters,
            })

    def _dispatch_log(self, **data: Any) -> None:
        """日志事件:转发到前端。"""
        if self.on_log:
            self.on_log(data)
