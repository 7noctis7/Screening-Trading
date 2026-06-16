from packages.common.event_bus import EventBus, Topic


def test_pub_sub():
    bus = EventBus()
    received = []
    bus.subscribe(Topic.SIGNAL_EMITTED, lambda e: received.append(e.payload))
    bus.publish(Topic.SIGNAL_EMITTED, {"instrument": "AAPL"})
    assert received == [{"instrument": "AAPL"}]


def test_no_subscriber_is_noop():
    bus = EventBus()
    bus.publish(Topic.KILL_SWITCH, "boom")  # ne doit pas lever
