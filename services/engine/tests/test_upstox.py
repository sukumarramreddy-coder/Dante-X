from dantex.providers.upstox import UpstoxNormalizer


def test_option_tick_normalization():
    x = UpstoxNormalizer.option_state("NSE_FO|1", {
        "firstLevelWithGreeks": {
            "ltpc": {"ltp": 101.5},
            "firstDepth": {"bidP": 101.4, "askP": 101.6},
            "optionGreeks": {"delta": .52, "gamma": .01, "theta": -8, "vega": 4, "iv": .13},
            "vtt": "5000", "oi": 10000,
        }
    })
    assert x["ltp"] == 101.5
    assert x["delta"] == .52
    assert x["oi"] == 10000
