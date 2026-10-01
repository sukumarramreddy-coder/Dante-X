import pytest

from dantex.providers.structure_live import _vwap


def test_available_volume_produces_vwap_without_a_proxy():
    rows = [{'high': 12, 'low': 8, 'close': 10, 'volume': 100},
            {'high': 22, 'low': 18, 'close': 20, 'volume': 300}]
    assert _vwap(rows) == (17.5, 'OK')


@pytest.mark.parametrize('volume', [0, -1, float('nan'), float('inf'), None])
def test_missing_or_invalid_volume_never_fabricates_vwap(volume):
    value, status = _vwap([{'high': 12, 'low': 8, 'close': 10, 'volume': volume}])
    assert value is None
    assert status.startswith('UNAVAILABLE_')
