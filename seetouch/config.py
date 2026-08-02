"""配置加载:.env + environment variables。

DEPRECATED: 使用 config_unified.UnifiedConfig 代替。
此文件保留以维持向后兼容。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# 向后兼容: 导出 load_env 和 AppSettings
from .config_unified import load_env as _load_env


def load_env(env_file: Path | str | None = None) -> None:
    """加载 .env 文件到 os.environ。

    DEPRECATED: 使用 config_unified.load_env 代替。
    """
    _load_env(env_file)


@dataclass
class AppSettings:
    """运行时配置（向后兼容）。

    DEPRECATED: 使用 config_unified.UnifiedConfig 代替。
    """

    device_serial: str | None
    runs_dir: Path
    max_steps: int
    log_level: str

    @classmethod
    def from_env(cls) -> "AppSettings":
        """从环境变量加载配置。

        DEPRECATED: 使用 config_unified.UnifiedConfig.from_env() 代替。
        """
        return cls(
            device_serial=(os.environ.get("SEETOUCH_DEVICE_SERIAL") or None),
            runs_dir=Path(os.environ.get("SEETOUCH_RUNS_DIR", "runs")),
            max_steps=int(os.environ.get("SEETOUCH_MAX_STEPS", "45")),
            log_level=os.environ.get("SEETOUCH_LOG_LEVEL", "INFO"),
        )
