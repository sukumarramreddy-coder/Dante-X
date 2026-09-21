from dantex.readiness import production_readiness


def test_unvalidated_system_remains_shadow():
    r = production_readiness(
        live_provider_connected=False,
        historical_validation_complete=False,
        calibration_publishable=False,
        ci_green=True,
    )
    assert not r.ready
    assert r.mode == "shadow"
    assert len(r.blockers) == 3
