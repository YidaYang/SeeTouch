"""环境自检:检查 adb / 设备 / uiautomator2 / VLM API key 是否到位。

用法:
    python -m seetouch.scripts.doctor
或者:
    python seetouch/scripts/doctor.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def check_adb() -> bool:
    print("\n[1/4] 检查 adb")
    if not shutil.which("adb"):
        _fail("adb 不在 PATH 里;请安装 Android Platform Tools")
        return False
    _ok("adb 可用")

    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=10,
        )
    except Exception as exc:
        _fail(f"`adb devices` 执行失败: {exc}")
        return False

    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    devices = [ln for ln in lines[1:] if "\tdevice" in ln]
    if not devices:
        _fail("未发现已授权的设备。检查 USB 调试是否开启、是否信任电脑")
        return False
    _ok(f"发现 {len(devices)} 台设备:\n         " + "\n         ".join(devices))
    return True


def check_uiautomator2() -> bool:
    print("\n[2/4] 检查 uiautomator2")
    try:
        import uiautomator2 as u2
    except ImportError:
        _fail("未安装 uiautomator2,请运行: pip install uiautomator2")
        return False
    _ok(f"uiautomator2 已安装 (version={getattr(u2, '__version__', '?')})")

    try:
        d = u2.connect()
    except Exception as exc:
        _fail(f"u2.connect() 失败: {exc}")
        _warn("如果是首次使用,先在终端运行: python -m uiautomator2 init")
        return False

    try:
        size = d.window_size()
        info = d.info
    except Exception as exc:
        _fail(f"读取设备信息失败: {exc}")
        return False

    _ok(f"屏幕尺寸 (像素): {size}")
    _ok(f"系统版本: {info.get('productName')} / Android {info.get('sdkInt')}")
    return True


def check_api_key() -> bool:
    print("\n[3/4] 检查 VLM API key")
    key = os.environ.get("VLM_API_KEY") or os.environ.get("DOUBAO_API_KEY")
    if not key:
        _fail("未设置 VLM_API_KEY (或 DOUBAO_API_KEY)。请在 .env 或环境变量里配置")
        return False
    _ok(f"API key 已设置 (前 6 位: {key[:6]}...)")
    api_url = os.environ.get("DOUBAO_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model_id = os.environ.get("DOUBAO_MODEL_ID", "doubao-seed-1-6-vision-250815")
    _ok(f"API URL:  {api_url}")
    _ok(f"Model ID: {model_id}")
    return True


def check_runs_dir() -> bool:
    print("\n[4/4] 检查产物目录")
    runs_dir = Path(os.environ.get("SEETOUCH_RUNS_DIR", "runs"))
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        _fail(f"无法创建产物目录 {runs_dir}: {exc}")
        return False
    _ok(f"产物目录可写: {runs_dir.resolve()}")
    return True


def main() -> int:
    # 自动加载 .env
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except ImportError:
        pass

    print("SeeTouch 环境自检")
    print("=" * 50)

    results = [
        check_adb(),
        check_uiautomator2(),
        check_api_key(),
        check_runs_dir(),
    ]

    print("\n" + "=" * 50)
    if all(results):
        print("所有检查通过,可以运行: python -m seetouch run \"<你的任务>\"")
        return 0
    print("有检查未通过,请按上面提示修复后重试")
    return 1


if __name__ == "__main__":
    sys.exit(main())
