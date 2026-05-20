"""命令行入口。

用法:
    python -m phone_agent run "<指令>"
    python -m phone_agent run "<指令>" --serial <设备serial>
    python -m phone_agent run "<指令>" --max-steps 30
"""

from __future__ import annotations

import argparse
import logging
import sys

from ..config import AppSettings, load_env
from ..core.runner import Runner
from ..core.task import Task
from ..device.android.controller import AndroidController
from ..logging_config import configure_logging
from ..reasoning.doubao import DoubaoReasoner
from ..safety.guard import Guard


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    load_env()
    settings = AppSettings.from_env()
    configure_logging(settings.log_level)

    if args.command == "run":
        return _cmd_run(args, settings)

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phone-agent", description="Android GUI Agent")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="执行一条自然语言任务")
    p_run.add_argument("instruction", help="用户任务指令,如:在哔哩哔哩搜索采莲曲")
    p_run.add_argument("--serial", default=None, help="Android 设备 serial(多设备时使用)")
    p_run.add_argument("--max-steps", type=int, default=None, help="单任务最大步数(默认 45)")
    p_run.add_argument("--runs-dir", default=None, help="运行产物输出目录(默认 ./runs)")

    return parser


def _cmd_run(args: argparse.Namespace, settings: AppSettings) -> int:
    serial = args.serial or settings.device_serial
    runs_dir = args.runs_dir or settings.runs_dir
    max_steps = args.max_steps or settings.max_steps

    try:
        device = AndroidController(serial=serial)
    except Exception as exc:
        logger.error("init android device failed: %s", exc)
        print(f"[ERROR] init android device failed: {exc}", file=sys.stderr)
        return 1

    try:
        reasoner = DoubaoReasoner()
    except Exception as exc:
        logger.error("init reasoner failed: %s", exc)
        print(f"[ERROR] init reasoner failed: {exc}", file=sys.stderr)
        return 1

    runner = Runner(
        device=device,
        reasoner=reasoner,
        guard=Guard(),
        runs_dir=runs_dir,
    )

    task = Task(instruction=args.instruction, max_steps=max_steps)
    result = runner.run(task)

    print()
    print("============== 任务结果 ==============")
    print(f"task_id:        {result.task_id}")
    print(f"completed:      {result.completed}")
    print(f"aborted_reason: {result.aborted_reason or '-'}")
    print(f"total_steps:    {result.total_steps}")
    print(f"tokens (in/out): {result.total_input_tokens}/{result.total_output_tokens}")
    print(f"runs_dir:       {result.runs_dir}")
    return 0 if result.completed else 1


if __name__ == "__main__":
    sys.exit(main())
