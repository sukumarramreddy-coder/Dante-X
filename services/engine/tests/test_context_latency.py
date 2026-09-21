from dantex.context_latency import latency_weight


def test_delayed_global_context_cannot_fire_trigger():
    x = latency_weight(20)
    assert not x.usable_for_trigger
    assert x.maximum_weight == .5
