from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str
    redirect_uri: str
    authorize_url: str = "https://api.upstox.com/v2/login/authorization/dialog"


def authorization_url(config: OAuthConfig, *, state: str) -> str:
    if not state:
        raise ValueError("OAuth state is required")
    return config.authorize_url + "?" + urlencode({
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "state": state,
    })


def validate_callback(*, expected_state: str, returned_state: str, code: str | None) -> str:
    if not expected_state or returned_state != expected_state:
        raise ValueError("OAuth state mismatch")
    if not code:
        raise ValueError("authorization code missing")
    return code
