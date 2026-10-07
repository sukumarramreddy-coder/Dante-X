import pytest

from dantex.providers.auth import OAuthConfig, authorization_url, validate_callback


def test_oauth_url_contains_state_and_redirect():
    x = authorization_url(OAuthConfig("client", "http://localhost/callback"), state="nonce")
    assert "client_id=client" in x
    assert "state=nonce" in x
    assert "redirect_uri=" in x


def test_callback_rejects_state_mismatch():
    with pytest.raises(ValueError):
        validate_callback(expected_state="a", returned_state="b", code="code")
