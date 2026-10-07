from dantex.config import Settings


def test_default_mode_is_shadow(monkeypatch):
    monkeypatch.delenv("DANTEX_MODE", raising=False)
    assert Settings.from_env().mode == "shadow"
