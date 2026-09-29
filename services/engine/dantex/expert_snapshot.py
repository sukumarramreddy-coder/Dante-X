"""Bounded, allowlisted input shared by deterministic and optional expert review."""
from datetime import datetime, timedelta
import hashlib
import json

from .freshness import IST, gate
from .probability import finite_number

SYMBOLS = ("NIFTY", "BANKNIFTY")
LEG_FIELDS = ("instrument_key", "ltp", "bid_price", "ask_price", "spread_pct", "volume",
              "oi", "oi_change", "delta", "gamma", "theta", "vega", "iv")


def number(value):
    return float(value) if finite_number(value) else None


def select(source, fields):
    return {key: source.get(key) for key in fields}


def normalized_snapshot(options, structures, families, *, now=None, position=None):
    now = (now or datetime.now(IST)).astimezone(IST)
    missing = []
    indices = {}
    for symbol in SYMBOLS:
        option, structure = options.get(symbol, {}), structures.get(symbol, {})
        path = option.get("path_response") or {}
        gates = [gate(source=symbol, timestamp=path.get("last_sample_at"),
                      provider_fresh=option.get("evidence_eligible") is True, now=now),
                 gate(source=symbol, timestamp=structure.get("last_candle_ts"),
                      provider_fresh=structure.get("evidence_eligible") is True, now=now)]
        if not all(g["eligible"] for g in gates):
            missing.append(f"{symbol}.freshness")
        # Use only closed, ordered, same-session bars. Never hand raw streams to the expert.
        bars = []
        for row in structure.get("recent_candles", [])[-120:]:
            try:
                at = datetime.fromisoformat(row["ts"])
                if at.tzinfo is None or at.astimezone(IST).date() != now.date():
                    continue
                if at + timedelta(minutes=1) > now:
                    continue
                if bars and at <= datetime.fromisoformat(bars[-1]["ts"]):
                    raise ValueError("unordered candles")
                values = [number(row.get(k)) for k in ("open", "high", "low", "close")]
                if any(v is None or v <= 0 for v in values):
                    continue
                if not values[2] <= min(values[0], values[3]) <= max(values[0], values[3]) <= values[1]:
                    continue
                bars.append({"ts": at.isoformat(), **dict(zip(("open", "high", "low", "close"), values))})
            except (ValueError, TypeError, KeyError):
                missing.append(f"{symbol}.closed_bars")
                bars = []
                break
        legs = []
        for row in option.get("strikes", [])[:11]:
            for side, key in (("CE", "call"), ("PE", "put")):
                raw = row.get(key) or {}
                leg = {k: number(raw.get(k)) for k in LEG_FIELDS if k != "instrument_key"}
                identity = raw.get("instrument_key")
                leg.update(instrument_key=identity if isinstance(identity, str) and len(identity) <= 100 else None,
                           side=side, strike=number(row.get("strike")),
                           execution_score=number((raw.get("quality") or {}).get("execution_score")))
                legs.append(leg)
        for field in ("delta", "gamma", "theta", "vega", "iv"):
            if not legs or any(l[field] is None for l in legs):
                missing.append(f"{symbol}.{field}")
        if option.get("derivatives_evidence_eligible") is not True:
            missing.append(f"{symbol}.verified_greeks")
        if not bars:
            missing.append(f"{symbol}.closed_bars")
        expiry = option.get("expiry")
        try:
            expiry_at = datetime.fromisoformat(expiry).replace(hour=15, minute=30, tzinfo=IST)
            minutes_to_expiry = (expiry_at - now).total_seconds() / 60
        except (TypeError, ValueError):
            expiry, minutes_to_expiry = None, None
            missing.append(f"{symbol}.expiry")
        if minutes_to_expiry is not None and minutes_to_expiry <= 0:
            missing.append(f"{symbol}.expired_contract")
        if number(option.get("spot")) is None or number(option.get("spot")) <= 0:
            missing.append(f"{symbol}.spot")
        indices[symbol] = {
            "spot": number(option.get("spot")), "expiry": expiry,
            "minutes_to_expiry": minutes_to_expiry,
            "expiry_day": expiry == now.date().isoformat(),
            "fresh": all(g["eligible"] for g in gates),
            "source_timestamps": [path.get("last_sample_at"), structure.get("last_candle_ts")],
            "structure": select(structure, ("trend", "opening_range", "opening_range_state",
                                           "prior_day", "vwap", "ema11", "ema46", "ema120", "atr14")),
            "closed_bars": bars, "legs": legs,
            "path": select(path, ("state", "spot_change", "atm_call_change_pct", "atm_put_change_pct")),
        }
        for field in ("vwap", "ema11", "ema46", "ema120", "prior_day"):
            if indices[symbol]["structure"][field] is None:
                missing.append(f"{symbol}.{field}")
    context = {}
    for name in ("breadth", "sector_leadership", "volatility"):
        family = (families.get("families") or {}).get(name) or {}
        fresh = (families.get("freshness", {}).get(name) or {}).get("eligible") is True
        context[name] = {"state": family.get("state") if fresh else "UNAVAILABLE"}
        if not fresh:
            missing.append(name)
    # Unconnected sources are explicit, never manufactured from unrelated proxies.
    unavailable = ["bank_constituents", "private_psu_divergence", "usdinr", "crude", "yields", "news"]
    missing.extend(unavailable)
    snapshot = {
        "schema_version": "1.0", "timestamp": now.isoformat(),
        "session": {"minutes_since_open": (now - now.replace(hour=9, minute=15, second=0, microsecond=0)).total_seconds()/60,
                    "minutes_to_close": (now.replace(hour=15, minute=30, second=0, microsecond=0)-now).total_seconds()/60,
                    "decision_checkpoint_reached": (now.hour, now.minute) >= (11, 0)},
        "indices": indices, "context": context,
        "position": position, "missing_data": sorted(set(missing)),
        "calibration_status": "UNCALIBRATED", "calibrated_probability": None,
    }
    snapshot["snapshot_id"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return snapshot
