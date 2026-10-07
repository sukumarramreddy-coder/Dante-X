import pytest

from dantex.providers.credentials import UpstoxCredentials


def test_analytics_token_loaded_only_from_runtime_environment(monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "secret-at-runtime")
    x = UpstoxCredentials.from_env()
    assert x.bearer_header()["Authorization"] == "Bearer secret-at-runtime"


def test_missing_token_fails_closed(monkeypatch):
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        UpstoxCredentials.from_env()
