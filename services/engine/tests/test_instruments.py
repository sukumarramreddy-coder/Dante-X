from datetime import date

from dantex.providers.instruments import build_universe, normalize_instrument
from dantex.providers.universe import classify


def test_instrument_key_is_canonical_identity():
    x = normalize_instrument({
        "instrument_key": "NSE_FO|123", "exchange_token": "999",
        "trading_symbol": "NIFTY26SEP23500PE", "name": "NIFTY",
        "segment": "NSE_FO", "exchange": "NSE", "instrument_type": "PE",
        "expiry": "2026-09-29", "strike_price": 23500, "lot_size": 65,
    })
    assert x.instrument_key == "NSE_FO|123"
    assert x.strike == 23500


def test_expired_derivative_is_removed_from_active_universe():
    rows = [{
        "instrument_key": "NSE_FO|1", "trading_symbol": "OLD", "name": "NIFTY",
        "segment": "NSE_FO", "exchange": "NSE", "instrument_type": "PE",
        "expiry": "2026-09-20", "strike_price": 23000, "lot_size": 65,
    }, {
        "instrument_key": "NSE_FO|2", "trading_symbol": "LIVE", "name": "NIFTY",
        "segment": "NSE_FO", "exchange": "NSE", "instrument_type": "CE",
        "expiry": "2026-09-22", "strike_price": 23500, "lot_size": 65,
    }]
    u = classify(build_universe(rows), today=date(2026, 9, 21))
    assert [x.instrument_key for x in u.options] == ["NSE_FO|2"]
