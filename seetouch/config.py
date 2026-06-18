"""配置加载:.env + environment variables。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env(env_file: Path | str | None = None) -> None:
    """加载 .env 文件到 os.environ。

    优先级:已存在的环境变量 > .env 文件。这样开发者临时 export 的值不会被覆盖。
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    if env_file:
        load_dotenv(env_file, override=False)
    else:
        # 自动找当前目录及父目录的 .env
        load_dotenv(override=False)


@dataclass
class AppSettings:
    """运行时配置。"""

    device_serial: str | None
    runs_dir: Path
    max_steps: int
    log_level: str

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            device_serial=(os.environ.get("SEETOUCH_DEVICE_SERIAL") or None),
            runs_dir=Path(os.environ.get("SEETOUCH_RUNS_DIR", "runs")),
            max_steps=int(os.environ.get("SEETOUCH_MAX_STEPS", "45")),
            log_level=os.environ.get("SEETOUCH_LOG_LEVEL", "INFO"),
        )
