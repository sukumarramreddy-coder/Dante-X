from dantex.contract_quality import assess_contract


def test_wide_spread_blocks_contract():
    assert not assess_contract(bid=90, ask=100, volume=1000, open_interest=5000).executable


def test_liquid_contract_passes():
    x = assess_contract(bid=99.5, ask=100, volume=5000, open_interest=10000)
    assert x.executable
    assert x.score > 70
