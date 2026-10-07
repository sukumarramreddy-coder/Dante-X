"""Oct 6 regression: V3 response clocks led the local clock by ~0.44s."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dantex.freshness import IST, gate
from dantex.providers.verified_option_quotes import verified_prices
from dantex.probability import evidence_prior

NOW = datetime(2026, 10, 6, 10, 0, tzinfo=IST)


@pytest.mark.parametrize("offset,eligible", [(-181, False), (-180, True),
    (0.564042, True), (1, True), (1.001, False), (60, False)])
def test_response_clock_skew_is_bounded_without_extending_stale_age(offset, eligible):
    stamp = (NOW + timedelta(seconds=offset)).isoformat()
    assert gate(source="V3_QUOTE", timestamp=stamp, now=NOW,
                quote_response=True)["eligible"] is eligible
    if offset > 0:
        assert not gate(source="PATH", timestamp=stamp, now=NOW)["eligible"]


@pytest.mark.parametrize("invalid", ["missing", "naive", "previous_session", "closed", "provider_stale"])
def test_response_allowance_preserves_other_gates(invalid):
    kwargs = {"source": "V3_QUOTE", "timestamp": NOW.isoformat(), "now": NOW,
                  "quote_response": True}
    if invalid == "missing": kwargs["timestamp"] = None
    elif invalid == "naive": kwargs["timestamp"] = NOW.replace(tzinfo=None).isoformat()
    elif invalid == "previous_session": kwargs["session_date"] = "2026-10-05"
    elif invalid == "closed": kwargs["now"] = NOW.replace(hour=16)
    else: kwargs["provider_fresh"] = False
    assert not gate(**kwargs)["eligible"]


@pytest.mark.parametrize("trade_offset", [-181, -1, 0, 0.001])
def test_option_response_skew_does_not_allow_future_or_stale_trades(trade_offset):
    response = (NOW + timedelta(seconds=0.564042)).isoformat()
    trade = str(int((NOW + timedelta(seconds=trade_offset)).timestamp()*1000))
    data = {key: {"instrument_token": key, "last_price": 100, "timestamp": response,
        "last_trade_time": trade, "depth": {"buy": [{"price": 99}], "sell": [{"price": 100}]}}
        for key in ("index", "call", "put")}
    strikes = [{"strike": 100, "call": {"instrument_key": "call"},
                            "put": {"instrument_key": "put"}}]
    if trade_offset < -180 or trade_offset > 0:
        with pytest.raises(ValueError):
            verified_prices(strikes, "index", {"data": data}, now=NOW)
    else:
        rows, spot, stamp = verified_prices(strikes, "index", {"data": data}, now=NOW)
        assert datetime.fromisoformat(stamp) <= NOW
        assert spot == 100
        assert rows[0]["call"]["greeks_evidence_eligible"] is False


@pytest.mark.parametrize("offset,ready", [(-0.4187775, True), (0.564042, True), (1.001, False), (-181, False)])
def test_oct5_oct6_context_paths_restore_provisional_review(monkeypatch, offset, ready):
    from dantex import api
    from dantex import freshness
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return NOW.astimezone(tz) if tz else NOW
    monkeypatch.setattr(freshness, "datetime", Clock)
    monkeypatch.setattr(api.instrument_master, "refresh_async", lambda: None)
    monkeypatch.setattr(api.validation_recorder, "record_duel", Mock())
    monkeypatch.setattr(api, "paper_lifecycle", lambda *args: {})
    monkeypatch.setattr(api, "review_expert_safely", Mock())
    monkeypatch.setattr(api.UpstoxCredentials, "from_env", lambda: SimpleNamespace(analytics_token="test"))
    options = {s: {"status": "OK", "evidence_eligible": True, "path_response": {
        "state": "CE_STRENGTHENING", "spot_change": 10,
        "last_sample_at": NOW.isoformat(), "session_date": "2026-10-06"}}
        for s in ("NIFTY", "BANKNIFTY")}
    structure = {"status": "OK", "evidence_eligible": True, "trend": "BULLISH",
        "last_candle_ts": (NOW-timedelta(minutes=1)).isoformat(), "session_date": "2026-10-06"}
    monkeypatch.setattr(api, "structure_snapshot", lambda symbol: structure)
    def quotes(self, keys):
        return {"data": {key: {"last_price": 100, "net_change": 0,
            "timestamp": (NOW+timedelta(seconds=offset)).isoformat()} for key in keys}}
    monkeypatch.setattr(api.UpstoxRestClient, "full_market_quotes", quotes)
    result = api.evaluate_option_duel(options["NIFTY"], options["BANKNIFTY"])
    families = result["evidence_families"]
    assert families["readiness"]["live_evidence_ready"] is ready
    for name in ("breadth", "sector_leadership", "volatility"):
        assert families["freshness"][name]["eligible"] is ready
    review = evidence_prior(families, families["readiness"])
    assert review["fresh_evidence"] is ready
    assert review["status"] == ("PROVISIONAL" if ready else "PRIOR_ONLY")
    assert review["directional"]["ce"] > 50 if ready else review["directional"]["ce"] == 50
    assert review["authorization"] == "NONE"
    assert review["read_only"] is True
    assert review["calibrated"] is review["calibration_ready"] is review["auto_execution"] is False
    assert result["mode"] == "shadow"
