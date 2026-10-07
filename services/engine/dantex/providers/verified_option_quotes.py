"""Replace chain prices with identity-matched, timestamped V3 quote observations.

Chain Greeks/IV remain unverified context; a response timestamp is NOT an
exchange trade timestamp. Both response time and last-trade time are checked.
"""
from datetime import datetime, timezone
from copy import deepcopy

from ..freshness import gate
from ..probability import finite_number


def verified_prices(strikes, underlying_key, payload, *, now=None):
    now = now or datetime.now(timezone.utc)
    raw = payload.get("data") or {}
    if not isinstance(raw, dict):
        raise TypeError("invalid quote payload")
    quotes = {}
    for key, item in raw.items():
        if isinstance(item, dict):
            identity = item.get("instrument_token") or (key if key == underlying_key else None)
            if identity in quotes:
                raise ValueError("duplicate quote identity")
            quotes[identity] = item
    output = deepcopy(strikes)
    stamps = []

    def quote(key, *, option):
        item = quotes.get(key) or {}
        stamp = item.get("timestamp")
        if not gate(source="V3_QUOTE", timestamp=stamp, now=now, quote_response=True)["eligible"]:
            raise ValueError("missing, stale or future quote response")
        if not finite_number(item.get("last_price")) or item["last_price"] <= 0:
            raise ValueError("invalid quote price")
        if option:
            try:
                trade = datetime.fromtimestamp(int(item["last_trade_time"]) / 1000, timezone.utc)
            except (KeyError, ValueError, TypeError, OverflowError, OSError) as exc:
                raise ValueError("missing option trade timestamp") from exc
            if not 0 <= (now - trade).total_seconds() <= 180:
                raise ValueError("stale or future option trade")
            stamps.append(trade)
        stamps.append(datetime.fromisoformat(stamp.replace("Z", "+00:00")))
        return item

    spot = quote(underlying_key, option=False)["last_price"]
    for row in output:
        for side in ("call", "put"):
            leg = row[side]
            item = quote(leg.get("instrument_key"), option=True)
            depth = item.get("depth") or {}
            buy, sell = depth.get("buy") or [], depth.get("sell") or []
            bid = buy[0].get("price") if buy else None
            ask = sell[0].get("price") if sell else None
            if not all(finite_number(x) for x in (bid, ask)) or not 0 < bid <= ask:
                raise ValueError("invalid option depth")
            leg.update(ltp=item["last_price"], bid_price=bid, ask_price=ask,
                       spread=ask-bid, spread_pct=100*(ask-bid)/item["last_price"],
                       volume=item.get("volume"), oi=item.get("oi"),
                       price_timestamp=item["timestamp"], last_trade_time=item["last_trade_time"],
                       greeks_evidence_eligible=False)
    return output, spot, min(stamps).isoformat()
