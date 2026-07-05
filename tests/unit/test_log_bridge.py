"""LogBridge 单元测试。"""

import logging

from seetouch.core.event_bus import EventBus, LOG
from seetouch.core.log_bridge import LogBridge


def test_log_bridge_forwards_log_records():
    """LogBridge 安装后,logging 记录应转发为 EventBus LOG 事件。"""
    bus = EventBus()
    received = []
    bus.subscribe(LOG, lambda **kw: received.append(kw))

    bridge = LogBridge(bus)
    bridge.install()

    logger = logging.getLogger("seetouch.test_bridge")
    logger.setLevel(logging.DEBUG)
    logger.info("hello from test")

    bridge.uninstall()

    assert len(received) == 1
    assert received[0]["level"] == "INFO"
    assert received[0]["name"] == "seetouch.test_bridge"
    assert "hello from test" in received[0]["message"]
    assert "timestamp" in received[0]


def test_log_bridge_uninstall_stops_forwarding():
    """卸载后不再转发。"""
    bus = EventBus()
    received = []
    bus.subscribe(LOG, lambda **kw: received.append(kw))

    bridge = LogBridge(bus)
    bridge.install()
    bridge.uninstall()

    logger = logging.getLogger("seetouch.test_uninstall")
    logger.setLevel(logging.DEBUG)
    logger.info("should not appear")

    assert len(received) == 0


def test_log_bridge_install_is_idempotent():
    """重复 install 不会注册多个 handler。"""
    bus = EventBus()
    received = []
    bus.subscribe(LOG, lambda **kw: received.append(kw))

    bridge = LogBridge(bus)
    bridge.install()
    bridge.install()  # 第二次应是空操作

    logger = logging.getLogger("seetouch.test_idempotent")
    logger.setLevel(logging.DEBUG)
    logger.info("once")

    bridge.uninstall()

    # 只收到一条,不是两条
    assert len(received) == 1


def test_log_bridge_uninstall_is_idempotent():
    """重复 uninstall 不报错。"""
    bus = EventBus()
    bridge = LogBridge(bus)
    bridge.install()
    bridge.uninstall()
    bridge.uninstall()  # 第二次应是空操作,无异常


def test_log_bridge_captures_warning_and_error():
    """WARNING 和 ERROR 级别的日志也能正确捕获。"""
    bus = EventBus()
    received = []
    bus.subscribe(LOG, lambda **kw: received.append(kw))

    bridge = LogBridge(bus)
    bridge.install()

    logger = logging.getLogger("seetouch.test_levels")
    logger.setLevel(logging.DEBUG)
    logger.warning("warn msg")
    logger.error("err msg")

    bridge.uninstall()

    assert len(received) == 2
    assert received[0]["level"] == "WARNING"
    assert received[1]["level"] == "ERROR"


def test_log_bridge_does_not_capture_outside_seetouch():
    """非 seetouch 命名空间的日志不会被捕获。"""
    bus = EventBus()
    received = []
    bus.subscribe(LOG, lambda **kw: received.append(kw))

    bridge = LogBridge(bus)
    bridge.install()

    # 用一个非 seetouch 的 logger
    other_logger = logging.getLogger("other_package.test")
    other_logger.setLevel(logging.DEBUG)
    other_logger.info("should not be captured")

    bridge.uninstall()

    # seetouch 的 handler 只挂在 seetouch logger 上,
    # 但如果 other_package 的 propagate=True 且根 logger 没 handler,
    # 它不会流到 seetouch 的 handler。
    # 确保不会误捕获。
    seetouch_msgs = [r for r in received if "seetouch" not in r.get("name", "")]
    # 即使被捕获,也不应该有 other_package 的日志
    assert len(seetouch_msgs) == 0


def test_log_bridge_sets_propagate_false():
    """安装 LogBridge 后,seetouch logger 的 propagate 应为 False。"""
    bus = EventBus()
    bridge = LogBridge(bus)

    target = logging.getLogger("seetouch")
    original = target.propagate

    bridge.install()
    assert target.propagate is False

    bridge.uninstall()
    assert target.propagate == original


def test_log_bridge_no_duplicate_with_root_handler():
    """即使 root logger 有 handler,每条日志也只触发一次 EventBus LOG 事件。"""
    bus = EventBus()
    received = []
    bus.subscribe(LOG, lambda **kw: received.append(kw))

    # 模拟 configure_logging:root 上挂一个 handler
    root = logging.getLogger()
    import io as _io
    fake_stream = _io.StringIO()
    root_handler = logging.StreamHandler(fake_stream)
    root.addHandler(root_handler)
    original_level = root.level
    root.setLevel(logging.DEBUG)

    try:
        bridge = LogBridge(bus)
        bridge.install()

        logger = logging.getLogger("seetouch.test_no_dup")
        logger.setLevel(logging.DEBUG)
        logger.info("should appear exactly once")

        bridge.uninstall()

        # 关键断言:EventBus 只收到一条,不是两条
        assert len(received) == 1
        assert "should appear exactly once" in received[0]["message"]
    finally:
        root.removeHandler(root_handler)
        root.setLevel(original_level)


def test_log_bridge_stderr_handler_lifecycle():
    """install 时添加 stderr handler,uninstall 时移除。"""
    bus = EventBus()
    bridge = LogBridge(bus)

    target = logging.getLogger("seetouch")
    handlers_before = len(target.handlers)

    bridge.install()
    # 应新增 2 个 handler:EventBusLogHandler + StreamHandler
    assert len(target.handlers) == handlers_before + 2

    bridge.uninstall()
    # 应恢复到原始数量
    assert len(target.handlers) == handlers_before

