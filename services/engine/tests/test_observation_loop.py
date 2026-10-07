from dantex.observation_loop import ObservationLoop


def test_observation_loop_defaults_to_shadow_sampling():
    loop = ObservationLoop()
    snapshot = loop.snapshot()
    assert snapshot["state"] == "OFFLINE"
    assert snapshot["interval_seconds"] == 30
    assert snapshot["mode"] == "shadow"
