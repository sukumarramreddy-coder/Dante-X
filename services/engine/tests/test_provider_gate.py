from dantex.provider_gate import provider_gate
from dantex.providers.provider_state import ProviderState


def test_stale_provider_blocks_signal_authorization():
    assert not provider_gate(
        state=ProviderState.STALE, synchronized=True, instrument_fresh=True,
    ).allowed


def test_live_provider_still_requires_fresh_instrument():
    assert not provider_gate(
        state=ProviderState.LIVE, synchronized=True, instrument_fresh=False,
    ).allowed
