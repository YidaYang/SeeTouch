"""日志桥接:Python logging → EventBus。

把 seetouch 命名空间下所有模块的日志记录转发为 EventBus 'log' 事件,
让调试器前端可以实时展示与 CLI stderr 一致的日志流。

用法::

    from seetouch.core.event_bus import EventBus
    from seetouch.core.log_bridge import LogBridge

    bus = EventBus()
    bridge = LogBridge(bus)
    bridge.install()        # 挂载到 seetouch logger
    # ... 运行任务 ...
    bridge.uninstall()      # 任务结束时清理,避免 Handler 泄露
"""

from __future__ import annotations

import logging
import time

from .event_bus import LOG, EventBus


class _EventBusLogHandler(logging.Handler):
    """把 logging.LogRecord 转发为 EventBus 'log' 事件。

    每条日志记录会触发一次 ``bus.emit("log", ...)``。
    """

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__()
        self._event_bus = event_bus

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self._event_bus.emit(
                LOG,
                level=record.levelname,
                name=record.name,
                message=message,
                timestamp=record.created,
            )
        except Exception:
            # Handler 内部不能抛异常,否则 logging 框架会吞掉后续日志
            self.handleError(record)


class LogBridge:
    """管理 EventBusLogHandler 的生命周期。

    与调试任务的生命周期绑定:
    - ``install()`` 在任务开始时调用
    - ``uninstall()`` 在任务结束 / stop 时调用

    支持重复 install/uninstall(幂等),不会泄露 Handler。
    """

    # 挂载到 seetouch 命名空间的根 logger,这样 runner、device、
    # reasoner、guard 等所有子模块的日志都会被捕获。
    _LOGGER_NAME = "seetouch"

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._handler = _EventBusLogHandler(event_bus)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        )
        self._installed = False

    def install(self) -> None:
        """把 Handler 挂到 seetouch logger。幂等。"""
        if self._installed:
            return
        target_logger = logging.getLogger(self._LOGGER_NAME)
        target_logger.addHandler(self._handler)
        self._installed = True

    def uninstall(self) -> None:
        """从 seetouch logger 移除 Handler。幂等。"""
        if not self._installed:
            return
        target_logger = logging.getLogger(self._LOGGER_NAME)
        target_logger.removeHandler(self._handler)
        self._installed = False
