from __future__ import annotations

from urllib.error import HTTPError, URLError

from fastapi import FastAPI

from .providers.credentials import UpstoxCredentials
from .providers.upstox import UpstoxConfig
from .providers.upstox_rest import UpstoxRestClient
from .radar import RadarInputs, opportunity_score

app = FastAPI(title="Dante X Engine", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "dante-x-engine"}


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
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_data_readable": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "http_status": exc.code,
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

