"""主循环 Runner:把 device / reasoner / guard / session 串成闭环。"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from ..core.action import (
    ACTION_CLICK,
    ACTION_COMPLETE,
    ACTION_OPEN,
    ACTION_SCROLL,
    ACTION_TYPE,
    ACTION_WAIT,
    Action,
)
from ..device.base import DeviceController, DeviceError, OpenAppNeedsVisual
from ..reasoning.base import Reasoner
from ..safety.guard import Guard
from .session import RunResult, Session
from .task import Task


logger = logging.getLogger(__name__)


class Runner:
    """单任务执行器。

    单步流程:
        1. 截屏 + 落盘
        2. Reasoner 预测 -> ActionOutput
        3. Guard 检查是否敏感动作,需要的话向用户确认
        4. 执行动作(COMPLETE 直接结束)
        5. 记录到 Session
        6. 检查终止条件:任务完成 / 用户拒绝 / 连续失败 / 步数耗尽
    """

    def __init__(
        self,
        device: DeviceController,
        reasoner: Reasoner,
        guard: Guard | None = None,
        runs_dir: Path | str = "runs",
        max_consecutive_failures: int = 2,
        max_consecutive_identical_actions: int = 3,
    ):
        self.device = device
        self.reasoner = reasoner
        self.guard = guard or Guard()
        self.runs_dir = Path(runs_dir)
        self.max_consecutive_failures = max_consecutive_failures
        self.max_consecutive_identical_actions = max_consecutive_identical_actions

    def run(self, task: Task) -> RunResult:
        session = Session(task, base_dir=self.runs_dir)
        logger.info(
            "start task: id=%s instruction=%r runs_dir=%s",
            task.task_id, task.instruction, session.dir,
        )

        # 视觉兜底状态:被设备层 raise OpenAppNeedsVisual 后,记下原始请求和当前桌面 package。
        # 下一步起每次执行后检测前台变化,首次切到非桌面 app 时回写 learned cache。
        pending_visual_request: str | None = None
        visual_baseline_app: str | None = None

        for step in range(1, task.max_steps + 1):
            try:
                screenshot = self.device.screenshot()
            except Exception as exc:
                logger.error("screenshot failed: %s", exc)
                session.mark_aborted(f"screenshot_failed: {exc}")
                break

            screenshot_path = session.save_screenshot(step, screenshot)

            out = self.reasoner.predict(task.instruction, screenshot, session.history)
            logger.info(
                "[step %d] action=%s params=%s",
                step, out.action.type, out.action.parameters,
            )

            # COMPLETE 不需要 guard,也不执行任何设备动作
            if out.action.type == ACTION_COMPLETE:
                session.record_step(step, out, execution_success=True, screenshot_path=screenshot_path)
                session.mark_completed()
                logger.info("task completed at step %d", step)
                break

            # 敏感动作拦截
            if self.guard.needs_confirmation(task, out):
                approved = self.guard.ask(out, screenshot_path=str(screenshot_path))
                if not approved:
                    session.record_step(
                        step, out, execution_success=None,
                        notes=["user_denied_sensitive_action"],
                        screenshot_path=screenshot_path,
                    )
                    session.mark_aborted("user_denied")
                    break

            # 执行
            notes: list[str] = []
            success: bool | None
            try:
                self._execute(out.action)
                success = True
            except OpenAppNeedsVisual as exc:
                notes.append(
                    f"❗ OPEN '{exc.requested}' 失败:静态表/包名直通/别名都未命中,"
                    f"系统已回桌面。本步绝对不要再 OPEN 同名 app,必须 CLICK 桌面图标"
                    f"(找不到时 SCROLL 水平翻页或上滑打开应用抽屉)。"
                )
                # 设备已回桌面,下一步交给 Reasoner 视觉处理;不算失败
                success = True
                pending_visual_request = exc.requested
                visual_baseline_app = self._safe_current_app()
                logger.info(
                    "visual fallback armed: request=%r baseline=%s",
                    pending_visual_request, visual_baseline_app,
                )
            except DeviceError as exc:
                logger.warning("device error at step %d: %s", step, exc)
                notes.append(f"device_error: {exc}")
                success = False
            except Exception as exc:
                logger.exception("unexpected error at step %d", step)
                notes.append(f"unexpected_error: {type(exc).__name__}: {exc}")
                success = False

            # 视觉兜底命中检测:每步执行后看前台是否切到了非桌面 app
            if pending_visual_request and out.action.type != ACTION_OPEN:
                current = self._safe_current_app()
                if current and current != visual_baseline_app:
                    try:
                        self.device.learn_app_from_visual(pending_visual_request, current)
                        notes.append(f"visual_fallback_learned: {pending_visual_request} -> {current}")
                    except Exception as exc:
                        logger.warning("learn_app_from_visual failed: %s", exc)
                    pending_visual_request = None
                    visual_baseline_app = None

            session.record_step(
                step, out,
                execution_success=success,
                notes=notes,
                screenshot_path=screenshot_path,
            )

            if session.consecutive_failures() >= self.max_consecutive_failures:
                logger.warning("too many consecutive failures, abort")
                session.mark_aborted("consecutive_failures")
                break

            if session.consecutive_identical_actions() >= self.max_consecutive_identical_actions:
                logger.warning(
                    "stuck in loop: same action repeated %d times, abort",
                    session.consecutive_identical_actions(),
                )
                session.mark_aborted("stuck_loop")
                break
        else:
            session.mark_aborted("max_steps_reached")

        return session.summarize()

    def _safe_current_app(self) -> str | None:
        try:
            return self.device.current_app()
        except Exception as exc:
            logger.warning("device.current_app() failed: %s", exc)
            return None

    # ---------------------- 动作分派 ----------------------

    def _execute(self, action: Action) -> None:
        if action.type == ACTION_CLICK:
            x, y = action.parameters["point"]
            self.device.click(int(x), int(y))
        elif action.type == ACTION_TYPE:
            self.device.type_text(action.parameters["text"])
        elif action.type == ACTION_SCROLL:
            start = tuple(action.parameters["start_point"])
            end = tuple(action.parameters["end_point"])
            self.device.scroll(start, end)
        elif action.type == ACTION_OPEN:
            self.device.open_app(action.parameters["app_name"])
        elif action.type == ACTION_WAIT:
            seconds = action.parameters.get("seconds", 1.5)
            seconds = max(0.5, min(5.0, float(seconds)))  # 兜底:0.5-5 秒
            logger.info("WAIT %.1fs", seconds)
            time.sleep(seconds)
        elif action.type == ACTION_COMPLETE:
            pass
        else:
            raise DeviceError(f"unknown action type: {action.type}")
