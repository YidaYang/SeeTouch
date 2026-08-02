"""统一异常层级:定义项目中所有自定义异常。

设计原则:
  - 所有自定义异常继承自 SeeTouchError
  - 按模块/功能分类(配置、设备、推理、执行)
  - 提供上下文信息(context 字典)
  - 支持错误码(用于日志聚合和监控)
"""

from __future__ import annotations

from typing import Any


class SeeTouchError(Exception):
    """所有 SeeTouch 自定义异常的基类。

    Attributes:
        message: 人类可读的错误描述
        code: 错误码(用于日志聚合、监控告警)
        context: 错误上下文(便于调试)
    """

    def __init__(
        self,
        message: str,
        code: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} [{ctx_str}]"
        return self.message


# ==================== 配置错误 ====================


class ConfigError(SeeTouchError):
    """配置相关错误的基类。"""


class MissingConfigError(ConfigError):
    """必需的配置项缺失。"""

    def __init__(self, key: str, hint: str = ""):
        message = f"Missing required config: {key}"
        if hint:
            message += f" ({hint})"
        super().__init__(message, context={"key": key, "hint": hint})


class InvalidConfigError(ConfigError):
    """配置值非法。"""

    def __init__(self, key: str, value: Any, reason: str):
        super().__init__(
            f"Invalid config {key}={value!r}: {reason}",
            context={"key": key, "value": value, "reason": reason},
        )


# ==================== 设备控制错误 ====================


class DeviceError(SeeTouchError):
    """设备控制相关错误的基类。"""


class DeviceNotFoundError(DeviceError):
    """未找到设备或设备离线。"""

    def __init__(self, serial: str | None = None):
        msg = f"Device not found: {serial}" if serial else "No device found"
        super().__init__(msg, context={"serial": serial})


class DeviceActionError(DeviceError):
    """设备动作执行失败。"""

    def __init__(self, action: str, reason: str, details: dict[str, Any] | None = None):
        super().__init__(
            f"Device action failed: {action} ({reason})",
            context={"action": action, "reason": reason, **(details or {})},
        )


class AppNotInstalledError(DeviceError):
    """应用未安装。"""

    def __init__(self, package: str):
        super().__init__(f"App not installed: {package}", context={"package": package})


# ==================== 应用启动错误 ====================


class AppLaunchError(SeeTouchError):
    """应用启动相关错误的基类。"""


class OpenAppNotFound(AppLaunchError):
    """应用名未在索引中找到高置信匹配,需要候选反馈。

    Attributes:
        request: 用户请求的应用名
        suggestions: 模糊匹配的候选应用名列表
    """

    def __init__(self, request: str, suggestions: list[str] | None = None):
        self.request = request
        self.suggestions = suggestions or []
        msg = f"App not found: {request!r}"
        if self.suggestions:
            msg += f", try one of: {', '.join(self.suggestions)}"
        super().__init__(msg, context={"request": request, "suggestions": self.suggestions})


class OpenAppNeedsVisual(AppLaunchError):
    """应用名需要视觉兜底(索引不可用或多次候选反馈仍未命中)。

    Attributes:
        request: 用户请求的应用名
    """

    def __init__(self, request: str):
        self.request = request
        super().__init__(
            f"App launch needs visual fallback: {request!r}",
            context={"request": request},
        )


# ==================== 推理错误 ====================


class ReasoningError(SeeTouchError):
    """推理层错误的基类。"""


class VLMAPIError(ReasoningError):
    """VLM API 调用失败。"""

    def __init__(self, reason: str, api_response: str | None = None):
        super().__init__(
            f"VLM API error: {reason}",
            context={"reason": reason, "api_response": api_response},
        )


class ParseError(ReasoningError):
    """模型输出解析失败。"""

    def __init__(self, raw_output: str, reason: str):
        super().__init__(
            f"Failed to parse model output: {reason}",
            context={"raw_output": raw_output[:200], "reason": reason},
        )


# ==================== 执行错误 ====================


class ExecutionError(SeeTouchError):
    """任务执行相关错误的基类。"""


class MaxStepsExceededError(ExecutionError):
    """超过最大步数限制。"""

    def __init__(self, max_steps: int):
        super().__init__(
            f"Task aborted: exceeded max steps ({max_steps})",
            context={"max_steps": max_steps},
        )


class ConsecutiveFailuresError(ExecutionError):
    """连续失败次数过多。"""

    def __init__(self, count: int, max_count: int):
        super().__init__(
            f"Task aborted: {count} consecutive failures (max {max_count})",
            context={"count": count, "max_count": max_count},
        )


class DeadLoopDetectedError(ExecutionError):
    """检测到死循环(连续重复相同动作)。"""

    def __init__(self, action: str, count: int):
        super().__init__(
            f"Dead loop detected: action {action!r} repeated {count} times",
            context={"action": action, "count": count},
        )


# ==================== 安全错误 ====================


class SafetyError(SeeTouchError):
    """安全防护相关错误的基类。"""


class SensitiveActionBlocked(SafetyError):
    """敏感动作被拦截,等待用户确认。"""

    def __init__(self, action_type: str, reason: str):
        super().__init__(
            f"Sensitive action blocked: {action_type} ({reason})",
            context={"action_type": action_type, "reason": reason},
        )
