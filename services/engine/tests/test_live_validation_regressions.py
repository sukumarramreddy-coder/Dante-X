from types import SimpleNamespace

import pytest

from dantex.decision import shadow_decision
from dantex.evidence_families import recompute_consensus
from dantex.momentum import cross_index_momentum


def test_reported_zero_score_conflict_is_a_state_veto():
    families = {
        name: {"state": "PE", "ce": 0.0, "pe": weight}
        for name, weight in {
            "structure_location": 2, "options_response": 2,
            "cross_index": 1.5, "breadth": 1.5,
            "derivatives_positioning": 1.5,
        }.items()
    }
    families.update({name: {"state": "NEUTRAL", "ce": 0, "pe": 0}
                     for name in ("sector_leadership", "volatility")})
    families["momentum_velocity"] = cross_index_momentum(
        {"state": "PE", "pe": 2}, {"state": "CE", "ce": 1})
    consensus = recompute_consensus(families)
    assert consensus["family_counts"] == {"ce": 0, "pe": 5, "conflict": 1, "directional": 6}
    assert shadow_decision(consensus, {"live_evidence_ready": True}, {}) == {
        "status": "NO_SETUP", "authorization": "NONE", "reason": "family consensus CONFLICT"}

    # Resolution allows only shadow detection; freshness remains mandatory.
    families["momentum_velocity"] = cross_index_momentum({"state": "PE"}, {"state": "PE"})
    consensus = recompute_consensus(families)
    nifty = {"expiry": "2026-09-29", "strikes": [{"strike": 23200, "put": {
        "ltp": 104.45, "spread_pct": 1, "delta": -.5,
        "quality": {"execution_score": 90}, "instrument_key": "test"}}]}
    result = shadow_decision(consensus, {"live_evidence_ready": True}, nifty)
    assert (result["status"], result["direction"], result["authorization"]) == ("DETECTED", "PE", "SHADOW_ONLY")
    assert result["probability"] is None
    blocked = shadow_decision(consensus, {"live_evidence_ready": False}, nifty)
    assert blocked["authorization"] == "NONE"
    assert blocked["reason"] == "required live evidence not fresh"


@pytest.mark.parametrize("quote,expected", [
    ({"last_price": 98, "net_change": -2, "ohlc": {"close": 98}}, 100),
    ({"ltp": 105, "net_change": 5, "ohlc": {"close": 105}}, 100),
    ({"last_price": 100, "net_change": 0}, 100),
    ({"prev_close": 101, "ohlc": {"close": 98}}, 101),
    ({"prev_close_price": 102, "ohlc": {"close": 98}}, 102),
    ({"last_price": 98, "ohlc": {"close": 98}}, None),
])
def test_previous_close_never_uses_intraday_close(quote, expected):
    from dantex.api import _previous_close
    assert _previous_close(quote) == expected


@pytest.mark.parametrize("fresh", [True, False])
def test_api_normalizes_all_three_quote_paths_and_preserves_gates(monkeypatch, fresh):
    from dantex import api
    monkeypatch.setattr(api.instrument_master, "refresh_async", lambda: None)
    monkeypatch.setattr(api.options_intelligence, "snapshot", lambda symbol: {
        "status": "OK", "path_response": {}})
    monkeypatch.setattr(api, "structure_snapshot", lambda symbol: {})
    monkeypatch.setattr(api, "freshness_gate", lambda **kwargs: {
        "eligible": fresh, "reasons": [] if fresh else ["stale test quote"]})
    monkeypatch.setattr(api.UpstoxCredentials, "from_env", lambda: SimpleNamespace(analytics_token="test"))
    monkeypatch.setattr(api.validation_recorder, "record_duel", lambda *args: None)

    def quotes(self, keys):
        return {"data": {key: {"last_price": 98, "net_change": -2,
                                "ohlc": {"close": 98}, "timestamp": "2026-09-24T12:00:00+05:30"}
                         for key in keys}}
    monkeypatch.setattr(api.UpstoxRestClient, "full_market_quotes", quotes)
    result = api.option_duel()
    families = result["evidence_families"]["families"]
    if fresh:
        assert families["breadth"]["state"] == "PE"
        assert families["breadth"]["metrics"]["median_change_pct"] == -2
        assert families["sector_leadership"]["state"] == "PE"
        assert families["volatility"]["metrics"]["change_pct"] == -2
        assert families["volatility"]["state"] == "NEUTRAL"
    else:
        assert all(families[name]["state"] == "STALE_CONTEXT"
                   for name in ("breadth", "sector_leadership", "volatility"))
        assert result["decision"]["reason"] == "required live evidence not fresh"
    assert result["mode"] == "shadow"
    assert result["decision"]["authorization"] == "NONE"


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf"), True, "100", 0, -1])
def test_previous_close_rejects_invalid_direct_values(invalid):
    from dantex.api import _previous_close
    assert _previous_close({"prev_close": invalid, "ohlc": {"close": 100}}) is None
    assert _previous_close({"prev_close": invalid, "prev_close_price": 101}) == 101


@pytest.mark.parametrize("ltp,net", [
    (float("nan"), 1), (float("inf"), 1), (100, float("nan")),
    (100, float("inf")), (True, 0), (100, True), (0, -100),
    (-1, -101), (100, 100), (100, 101), (1e308, -1e308),
])
def test_invalid_reconstruction_falls_back_to_valid_direct_close(ltp, net):
    from dantex.api import _previous_close
    quote = {"last_price": ltp, "net_change": net, "ohlc": {"close": 100}}
    assert _previous_close(quote) is None
    assert _previous_close({**quote, "prev_close": 101}) == 101
