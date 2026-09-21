from __future__ import annotations

from urllib.error import HTTPError, URLError

from fastapi import FastAPI

from .providers.credentials import UpstoxCredentials
from .providers.upstox import UpstoxConfig
from .providers.upstox_rest import UpstoxRestClient
from .providers.upstox_live import nifty_live_probe
from .providers.upstox_core_live import core_live_feed
from .providers.upstox_master import instrument_master
from .providers.options_intelligence import options_intelligence
from .option_duel import duel
from .evidence_families import evidence_families
from .momentum import momentum_family, cross_index_momentum
from .breadth import breadth_family, sector_leadership_family, NIFTY_BREADTH_KEYS, SECTOR_INDEX_KEYS
from .observation_loop import observation_loop
from .providers.structure_live import structure_snapshot
from .radar import RadarInputs, opportunity_score

app = FastAPI(title="Dante X Engine", version="0.1.0")


@app.on_event("startup")
def start_shadow_observers():
    """Start read-only background observers with the service process."""
    core_live_feed.start()
    instrument_master.refresh_async()
    observation_loop.start()


@app.get("/health")
def health():
    return {"status": "ok", "service": "dante-x-engine"}


@app.get("/v1/structure/{symbol}")
def live_structure(symbol: str):
    """Read-only intraday structure: VWAP, OR, EMA, ATR and prior-day levels."""
    normalized = symbol.upper()
    if normalized not in {"NIFTY", "BANKNIFTY"}:
        return {"status": "UNSUPPORTED_SYMBOL", "symbol": normalized, "mode": "shadow"}
    try:
        return structure_snapshot(normalized)
    except Exception as exc:
        return {"symbol": normalized, "status": "DEGRADED", "error": f"{type(exc).__name__}: {str(exc)[:180]}", "mode": "shadow"}


@app.get("/v1/observation/status")
def observation_status():
    """Background SHADOW sampler health."""
    observation_loop.start()
    return observation_loop.snapshot()


@app.get("/v1/duel")
def option_duel():
    """SHADOW CE-vs-PE evidence duel across NIFTY and BANKNIFTY."""
    instrument_master.refresh_async()
    nifty = options_intelligence.snapshot("NIFTY")
    bank = options_intelligence.snapshot("BANKNIFTY")
    if nifty.get("status") != "OK" or bank.get("status") != "OK":
        return {"state": "DATA_NOT_READY", "nifty_status": nifty.get("status"), "banknifty_status": bank.get("status"), "mode": "shadow"}
    nifty_structure = structure_snapshot("NIFTY")
    bank_structure = structure_snapshot("BANKNIFTY")
    families = evidence_families(nifty, bank, nifty_structure, bank_structure)
    # Momentum is a live-session family. Historical fallback candles remain
    # visible as context but must never be reinterpreted as current velocity.
    if nifty_structure.get("evidence_eligible") is False:
        n_momentum = {"state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
                      "quality":{"freshness":nifty_structure.get("freshness"),"session_date":nifty_structure.get("session_date")},
                      "reasons":["historical structure candles blocked from live momentum"]}
    else:
        n_momentum = momentum_family(nifty_structure.get("recent_candles") or [])
    if bank_structure.get("evidence_eligible") is False:
        b_momentum = {"state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
                      "quality":{"freshness":bank_structure.get("freshness"),"session_date":bank_structure.get("session_date")},
                      "reasons":["historical structure candles blocked from live momentum"]}
    else:
        b_momentum = momentum_family(bank_structure.get("recent_candles") or [])
    families["families"]["nifty_momentum"] = n_momentum
    families["families"]["banknifty_momentum"] = b_momentum
    families["families"]["cross_index_momentum"] = cross_index_momentum(n_momentum, b_momentum)
    # Breadth is fetched independently from actual liquid constituents. Fail
    # closed on provider/shape errors; never turn missing breadth into a vote.
    try:
        client = UpstoxRestClient(UpstoxConfig(access_token=UpstoxCredentials.from_env().analytics_token))
        payload = client.full_market_quotes(NIFTY_BREADTH_KEYS)
        raw = (payload.get("data") or {})
        quotes = []
        for item in raw.values() if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            ohlc = item.get("ohlc") or {}
            quotes.append({
                "ltp": item.get("last_price") or item.get("ltp"),
                "prev_close": ohlc.get("close") or item.get("prev_close"),
            })
        families["families"]["breadth"] = breadth_family(quotes)
        sector_payload = client.full_market_quotes(list(SECTOR_INDEX_KEYS.values()))
        sector_raw = sector_payload.get("data") or {}
        sector_quotes = {}
        for name, key in SECTOR_INDEX_KEYS.items():
            # Provider response keys may use instrument token or symbol form;
            # match exact key first, then normalized instrument-token suffix.
            item = sector_raw.get(key)
            if item is None and isinstance(sector_raw, dict):
                item = next((v for k,v in sector_raw.items()
                             if isinstance(v,dict) and (k == key or v.get("instrument_token") == key)), None)
            if isinstance(item, dict):
                ohlc = item.get("ohlc") or {}
                sector_quotes[name] = {"ltp":item.get("last_price") or item.get("ltp"),
                                       "prev_close":ohlc.get("close") or item.get("prev_close")}
        families["families"]["sector_leadership"] = sector_leadership_family(sector_quotes)
    except Exception as exc:
        families["families"]["breadth"] = {
            "state":"UNAVAILABLE","ce":0.0,"pe":0.0,
            "quality":{"usable":0,"required":10},
            "reasons":[f"breadth provider unavailable: {type(exc).__name__}"],
        }
        families["families"]["sector_leadership"] = {
            "state":"UNAVAILABLE","ce":0.0,"pe":0.0,
            "quality":{"usable":0,"required":5},
            "reasons":[f"sector provider unavailable: {type(exc).__name__}"],
        }
    # Recompute consensus after runtime families are attached. DATA_QUALITY_BLOCK
    # and NEUTRAL families deliberately have zero directional voting power.
    directional = [v for v in families["families"].values() if v.get("state") in {"CE", "PE", "CONFLICT"}]
    ce_count = sum(v.get("state") == "CE" for v in directional)
    pe_count = sum(v.get("state") == "PE" for v in directional)
    conflict_count = sum(v.get("state") == "CONFLICT" for v in directional)
    families["family_counts"] = {"ce": ce_count, "pe": pe_count, "conflict": conflict_count, "directional": len(directional)}
    if conflict_count or (ce_count and pe_count):
        families["state"] = "CONFLICT"
    elif ce_count >= 2:
        families["state"] = "CE_EVIDENCE"
    elif pe_count >= 2:
        families["state"] = "PE_EVIDENCE"
    else:
        families["state"] = "NO_EDGE"
    return {
        "duel": duel(nifty, bank, nifty_structure, bank_structure),
        "evidence_families": families,
        "nifty": {"path": nifty["path_response"], "structure": nifty_structure},
        "banknifty": {"path": bank["path_response"], "structure": bank_structure},
        "mode": "shadow",
    }


@app.get("/v1/options/{symbol}")
def options_snapshot(symbol: str):
    """Nearest-expiry ATM neighborhood with read-only Upstox chain/Greeks."""
    normalized = symbol.upper()
    if normalized not in {"NIFTY", "BANKNIFTY"}:
        return {"status": "UNSUPPORTED_SYMBOL", "symbol": normalized, "mode": "shadow"}
    instrument_master.refresh_async()
    return options_intelligence.snapshot(normalized)


@app.get("/v1/market/state")
def market_state():
    """SHADOW core market state for NIFTY/BANKNIFTY plus instrument-master health."""
    core_live_feed.start()
    instrument_master.refresh_async()
    return {
        "feed": core_live_feed.snapshot(),
        "instrument_master": {
            "nifty": instrument_master.index_derivatives("NIFTY"),
            "banknifty": instrument_master.index_derivatives("BANKNIFTY"),
        },
        "mode": "shadow",
    }


@app.get("/v1/providers/upstox/live")
def upstox_live():
    """Start/read the SHADOW NIFTY V3 heartbeat. No order capability."""
    nifty_live_probe.start()
    return nifty_live_probe.snapshot()


@app.get("/v1/providers/upstox/diagnostic")
def upstox_diagnostic():
    """Safe read-only provider check. Never returns credentials or redirect URLs."""
    try:
        credentials = UpstoxCredentials.from_env()
    except RuntimeError:
        return {
            "provider": "upstox",
            "configured": False,
            "authenticated": False,
            "market_data_readable": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "detail": "analytics token is not configured",
        }

    client = UpstoxRestClient(UpstoxConfig(access_token=credentials.analytics_token))

    # Analytics-token authentication is proven with a documented read-only
    # market-data endpoint, not inferred from the websocket authorize helper.
    try:
        quote_payload = client.full_market_quote("NSE_INDEX|Nifty 50")
        quote_ok = str(quote_payload.get("status", "")).lower() == "success"
    except HTTPError as exc:
        upstox_error_code = None
        upstox_error_message = None
        try:
            import json
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            errors = body.get("errors") or []
            if errors and isinstance(errors[0], dict):
                upstox_error_code = errors[0].get("errorCode") or errors[0].get("error_code")
                upstox_error_message = errors[0].get("message")
        except Exception:
            pass
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_data_readable": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "http_status": exc.code,
            "upstox_error_code": upstox_error_code,
            "upstox_error_message": upstox_error_message,
            "detail": "Upstox rejected the read-only market-data probe",
        }
    except (URLError, TimeoutError):
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_data_readable": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "detail": "Upstox could not be reached",
        }
    except Exception:
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_data_readable": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "detail": "market-data diagnostic failed safely",
        }

    feed_authorized = False
    feed_http_status = None
    try:
        feed_payload = client.market_feed_authorize()
        feed_data = feed_payload.get("data") or {}
        feed_authorized = (
            str(feed_payload.get("status", "")).lower() == "success"
            and bool(feed_data.get("authorized_redirect_uri"))
        )
    except HTTPError as exc:
        feed_http_status = exc.code
    except Exception:
        pass

    return {
        "provider": "upstox",
        "configured": True,
        "authenticated": quote_ok,
        "market_data_readable": quote_ok,
        "market_feed_authorized": feed_authorized,
        "market_feed_authorize_http_status": feed_http_status,
        "mode": "shadow",
        "detail": (
            "analytics token authenticated for read-only market data"
            if quote_ok
            else "market-data response was incomplete"
        ),
    }

