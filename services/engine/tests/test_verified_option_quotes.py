from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from dantex.providers.verified_option_quotes import verified_prices

NOW = datetime(2026, 9, 29, 5, 0, tzinfo=timezone.utc)
UNDERLYING = "NSE_INDEX|Nifty 50"


def payload():
    return {"data": {key: {"instrument_token": key, "last_price": 100, "timestamp": NOW.isoformat(),
        "last_trade_time": str(int(NOW.timestamp()*1000)), "depth": {"buy": [{"price": 99}], "sell": [{"price": 100}]}}
        for key in (UNDERLYING, "call", "put")}}


def strikes():
    return [{"strike": 25000, "call": {"instrument_key": "call", "ltp": 999}, "put": {"instrument_key": "put"}}]


def test_verified_quotes_replace_chain_prices_without_promoting_greeks():
    source = strikes()
    copy = deepcopy(source)
    rows, spot, stamp = verified_prices(source, UNDERLYING, payload(), now=NOW)
    assert source == copy
    assert spot == 100 and rows[0]["call"]["ltp"] == 100
    assert rows[0]["call"]["greeks_evidence_eligible"] is False
    assert stamp == NOW.isoformat()


@pytest.mark.parametrize("change", ["missing_identity", "stale_trade", "future_trade", "stale_response", "bad_depth", "missing_trade"])
def test_unproven_quotes_fail_closed(change):
    data = payload()
    item = data["data"]["call"]
    if change == "missing_identity":
        item["instrument_token"] = "unrelated"
    elif change == "stale_trade":
        item["last_trade_time"] = str(int((NOW-timedelta(minutes=10)).timestamp()*1000))
    elif change == "future_trade":
        item["last_trade_time"] = str(int((NOW+timedelta(seconds=1)).timestamp()*1000))
    elif change == "stale_response":
        item["timestamp"] = (NOW-timedelta(minutes=10)).isoformat()
    elif change == "bad_depth":
        item["depth"]["buy"][0]["price"] = 200
    else:
        item.pop("last_trade_time")
    with pytest.raises(ValueError):
        verified_prices(strikes(), UNDERLYING, data, now=NOW)
