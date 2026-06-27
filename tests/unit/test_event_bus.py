"""EventBus 单元测试。"""

from seetouch.core.event_bus import EventBus


def test_subscribe_and_emit():
    """订阅后 emit,handler 应被调用。"""
    bus = EventBus()
    results = []
    bus.subscribe("test", lambda x=None: results.append(x))
    bus.emit("test", x=42)
    assert results == [42]


def test_multiple_handlers():
    """同一事件可挂多个 handler,按注册顺序执行。"""
    bus = EventBus()
    order = []
    bus.subscribe("e", lambda **kw: order.append("a"))
    bus.subscribe("e", lambda **kw: order.append("b"))
    bus.emit("e")
    assert order == ["a", "b"]


def test_unsubscribe():
    """unsubscribe 后 handler 不再被调用。"""
    bus = EventBus()
    results = []
    handler = lambda **kw: results.append(1)
    bus.subscribe("e", handler)
    bus.emit("e")
    bus.unsubscribe("e", handler)
    bus.emit("e")
    assert results == [1]


def test_unsubscribe_nonexistent_is_safe():
    """unsubscribe 不存在的 handler 不报错。"""
    bus = EventBus()
    bus.unsubscribe("e", lambda: None)  # 无异常


def test_emit_no_subscribers():
    """emit 没有订阅者时不报错。"""
    bus = EventBus()
    bus.emit("nonexistent", x=1)  # 无异常


def test_handler_exception_does_not_stop_others():
    """一个 handler 抛异常不影响后续 handler。"""
    bus = EventBus()
    results = []

    def bad_handler(**kw):
        raise ValueError("boom")

    bus.subscribe("e", bad_handler)
    bus.subscribe("e", lambda **kw: results.append("ok"))
    bus.emit("e")
    assert results == ["ok"]


def test_emit_passes_kwargs():
    """emit 的关键字参数正确传递给 handler。"""
    bus = EventBus()
    received = {}
    bus.subscribe("e", lambda **kw: received.update(kw))
    bus.emit("e", step=3, screenshot="img")
    assert received == {"step": 3, "screenshot": "img"}


def test_clear():
    """clear 后所有订阅被清除。"""
    bus = EventBus()
    results = []
    bus.subscribe("a", lambda **kw: results.append("a"))
    bus.subscribe("b", lambda **kw: results.append("b"))
    bus.clear()
    bus.emit("a")
    bus.emit("b")
    assert results == []


def test_different_events_independent():
    """不同事件的订阅互相独立。"""
    bus = EventBus()
    results = []
    bus.subscribe("a", lambda **kw: results.append("a"))
    bus.subscribe("b", lambda **kw: results.append("b"))
    bus.emit("a")
    assert results == ["a"]
