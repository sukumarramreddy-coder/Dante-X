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
            "market_feed_authorized": False,
            "mode": "shadow",
            "detail": "analytics token is not configured",
        }

    client = UpstoxRestClient(UpstoxConfig(access_token=credentials.analytics_token))
    try:
        payload = client.market_feed_authorize()
    except HTTPError as exc:
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "http_status": exc.code,
            "detail": "Upstox rejected the read-only authorization request",
        }
    except (URLError, TimeoutError):
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "detail": "Upstox could not be reached",
        }
    except Exception:
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "detail": "provider diagnostic failed safely",
        }

    status = str(payload.get("status", "")).lower()
    data = payload.get("data") or {}
    authorized = status == "success" and bool(data.get("authorized_redirect_uri"))
    return {
        "provider": "upstox",
        "configured": True,
        "authenticated": status == "success",
        "market_feed_authorized": authorized,
        "mode": "shadow",
        "detail": "read-only market-feed authorization succeeded" if authorized else "authorization response was incomplete",
    }


@app.post("/v1/radar/score")
def radar_score(inputs: RadarInputs):
    return {
        "opportunity_score": opportunity_score(inputs),
        "is_probability": False,
        "label": "uncalibrated opportunity score",
    }
