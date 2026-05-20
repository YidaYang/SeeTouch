"""回放某次 session:读 trace.jsonl 打印每一步。

用法:
    python phone_agent/scripts/replay.py runs/<task_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def replay(session_dir: Path) -> int:
    trace_path = session_dir / "trace.jsonl"
    summary_path = session_dir / "summary.json"
    if not trace_path.exists():
        print(f"trace.jsonl not found in {session_dir}", file=sys.stderr)
        return 1

    print(f"=== Session: {session_dir} ===")

    for line in trace_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        step = rec.get("step", "?")
        atype = rec.get("action_type", "?")
        params = rec.get("parameters", {})
        scr = rec.get("screen_summary", "")
        act = rec.get("action_summary", "")
        success = rec.get("execution_success")
        notes = rec.get("notes") or []
        screenshot = rec.get("screenshot", "")

        print(f"\n--- Step {step}: {atype} {json.dumps(params, ensure_ascii=False)}")
        if scr:
            print(f"  屏幕: {scr}")
        if act:
            print(f"  操作: {act}")
        if success is False:
            print("  [x] 执行失败")
        elif success is True:
            print("  [v] 执行成功")
        if notes:
            for n in notes:
                print(f"  备注: {n}")
        if screenshot:
            print(f"  截图: {screenshot}")

    if summary_path.exists():
        print("\n=== Summary ===")
        print(summary_path.read_text(encoding="utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="回放 phone-agent session")
    parser.add_argument("session_dir", help="runs/<task_id> 目录路径")
    args = parser.parse_args()
    return replay(Path(args.session_dir))


if __name__ == "__main__":
    sys.exit(main())
