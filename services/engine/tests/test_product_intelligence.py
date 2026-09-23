from dantex.alerts import evidence_alert
from dantex.market_pulse import build_market_pulse


def test_market_pulse_is_app_facing_and_fail_closed():
    pulse = build_market_pulse(
        symbol="NIFTY",
        spot=23450.0,
        structure={"state": "BULLISH"},
        options={
            "path_response": {"state": "CE_STRENGTHENING"},
            "positioning": {"classification": "DESCRIPTIVE_ONLY"},
        },
        breadth={"state": "BULLISH"},
        volatility={"state": "NEUTRAL"},
        freshness={"eligible": True},
        counterweights=["call wall overhead"],
    )
    assert pulse.freshness == "LIVE"
    assert pulse.option_response == "CE_STRENGTHENING"
    assert pulse.counterweights == ("call wall overhead",)


def test_market_pulse_blocks_when_freshness_is_not_proven():
    pulse = build_market_pulse(
        symbol="NIFTY",
        spot=None,
        structure={},
        options={},
        breadth={},
        volatility={},
        freshness={"eligible": False},
    )
    assert pulse.freshness == "BLOCKED"


def test_evidence_alert_ignores_noise_and_reports_meaningful_change():
    assert evidence_alert(
        symbol="NIFTY", side="PE", previous_score=60, current_score=65, reasons=["minor move"]
    ) is None
    alert = evidence_alert(
        symbol="NIFTY",
        side="PE",
        previous_score=55,
        current_score=78,
        reasons=["VWAP lost", "BANKNIFTY confirms", "put premium strengthening"],
    )
    assert alert is not None
    assert alert.delta == 23
    assert alert.severity == "MEDIUM"
    assert "put premium strengthening" in alert.reasons
