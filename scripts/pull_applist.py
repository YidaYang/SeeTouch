"""helper APK 应用索引导出验证脚本(Stage 1 手动验证用)。

触发手机端 SeeTouch helper 导出 applist.json,轮询完成标记后 pull 到本地并解析。
文件通道不可用时自动从 logcat 兜底通道解码。

用法:
    python scripts/pull_applist.py
    python scripts/pull_applist.py --serial <设备序列号> --out ./applist.json
    python scripts/pull_applist.py --channel logcat   # 强制走 logcat 通道
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

HELPER_PACKAGE = "com.seetouch.app"
HELPER_ACTIVITY = f"{HELPER_PACKAGE}/.helper.AppListExportActivity"
DEVICE_DIR = f"/sdcard/Android/data/{HELPER_PACKAGE}/files"
DEVICE_JSON = f"{DEVICE_DIR}/applist.json"
DEVICE_DONE = f"{DEVICE_DIR}/applist.json.done"
LOGCAT_TAG = "SEETOUCH_APPLIST"


def adb(serial: str | None, *args: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def trigger_export(serial: str | None, channel: str) -> None:
    result = adb(
        serial,
        "shell", "am", "start", "-n", HELPER_ACTIVITY,
        "--es", "channels", channel,
    )
    if result.returncode != 0 or "Error" in result.stdout + result.stderr:
        raise RuntimeError(
            f"启动 helper Activity 失败,请确认 APK 已安装:\n{result.stdout}{result.stderr}"
        )


def wait_done_marker(serial: str | None, timeout_seconds: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = adb(serial, "shell", "cat", DEVICE_DONE)
        if result.returncode == 0 and result.stdout.strip().startswith("{"):
            return json.loads(result.stdout.strip())
        time.sleep(0.5)
    raise TimeoutError(f"等待 {DEVICE_DONE} 超时({timeout_seconds}s)")


def pull_json(serial: str | None, out_path: Path) -> dict:
    result = adb(serial, "pull", DEVICE_JSON, str(out_path), timeout=60.0)
    if result.returncode != 0:
        raise RuntimeError(f"adb pull 失败:\n{result.stdout}{result.stderr}")
    return json.loads(out_path.read_text(encoding="utf-8"))


def decode_from_logcat(serial: str | None, out_path: Path) -> dict:
    """从 logcat 兜底通道解码(行协议: BEGIN n / CHUNK i/n <b64> / END size)。"""
    result = adb(serial, "logcat", "-d", "-s", f"{LOGCAT_TAG}:I", timeout=60.0)
    if result.returncode != 0:
        raise RuntimeError(f"读取 logcat 失败:\n{result.stderr}")

    chunks: dict[int, str] = {}
    total = None
    for line in result.stdout.splitlines():
        if f"{LOGCAT_TAG}" not in line:
            continue
        payload = line.split(f"{LOGCAT_TAG}", 1)[1].lstrip(": ").strip()
        if payload.startswith("BEGIN "):
            chunks.clear()
            total = int(payload.split()[1])
        elif payload.startswith("CHUNK "):
            _, index_part, data = payload.split(" ", 2)
            index = int(index_part.split("/")[0])
            chunks[index] = data
    if total is None or len(chunks) != total:
        raise RuntimeError(
            f"logcat 通道数据不完整(期望 {total} 块,收到 {len(chunks)} 块);"
            f"请先用 --channel logcat 重新触发导出"
        )

    encoded = "".join(chunks[i] for i in range(1, total + 1))
    data = json.loads(base64.b64decode(encoded).decode("utf-8"))
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def summarize(data: dict) -> None:
    apps = data.get("apps", [])
    print(f"schema_version : {data.get('schema_version')}")
    print(f"generated_at   : {data.get('generated_at')}")
    device = data.get("device", {})
    print(f"device         : {device.get('manufacturer')} {device.get('model')} (SDK {device.get('sdk_int')})")
    print(f"count          : {data.get('count')}")
    print("\n示例条目(前 10 个非系统应用):")
    shown = 0
    for app in apps:
        if app.get("system"):
            continue
        print(f"  {app['label']}  ->  {app['package']}")
        shown += 1
        if shown >= 10:
            break


def main() -> int:
    parser = argparse.ArgumentParser(description="触发并拉取 helper APK 的应用索引")
    parser.add_argument("--serial", default=None, help="多设备时指定序列号")
    parser.add_argument("--out", default="applist.json", help="本地输出路径")
    parser.add_argument(
        "--channel", default="file", choices=["file", "logcat"],
        help="导出通道(默认 file,pull 不可用时用 logcat)",
    )
    args = parser.parse_args()
    out_path = Path(args.out)

    print(f"[1/3] 触发导出(channel={args.channel})...")
    trigger_export(args.serial, args.channel)

    if args.channel == "file":
        print("[2/3] 等待完成标记...")
        status = wait_done_marker(args.serial)
        print(f"      {status}")
        print(f"[3/3] 拉取 {DEVICE_JSON} -> {out_path}")
        data = pull_json(args.serial, out_path)
    else:
        print("[2/3] 等待导出完成...")
        time.sleep(3.0)
        print(f"[3/3] 从 logcat 解码 -> {out_path}")
        data = decode_from_logcat(args.serial, out_path)

    print()
    summarize(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
