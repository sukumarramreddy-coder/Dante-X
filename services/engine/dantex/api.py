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
    return {"duel": duel(nifty, bank), "nifty": nifty["path_response"], "banknifty": bank["path_response"], "mode": "shadow"}


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

