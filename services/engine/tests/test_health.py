from datetime import datetime, timezone

from dantex.health import snapshot
from dantex.providers.provider_state import ProviderState


def test_shadow_mode_never_reports_signal_authorization():
    x = snapshot(
        mode="shadow", provider_state=ProviderState.LIVE,
        authorization_allowed=True, now=datetime.now(timezone.utc),
    )
    assert not x.signal_authorization
