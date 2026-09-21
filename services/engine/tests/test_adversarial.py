from dantex.adversarial import Threat, assess_threat
from dantex.divergence import DivergenceState


def test_option_refusal_blocks_entry():
    x = assess_threat(
        trigger=101, current=101, invalidation=98, prior_extreme=100,
        potential_score=80, divergence=DivergenceState.UNDERLYING_ONLY,
    )
    assert x.threat == Threat.OPTION_DIVERGENCE
    assert x.block_entry


def test_gap_through_is_not_chased():
    x = assess_threat(
        trigger=101, current=106, invalidation=98, prior_extreme=100,
        potential_score=80,
    )
    assert x.threat == Threat.GAP_THROUGH


def test_spent_move_is_blocked():
    x = assess_threat(
        trigger=101, current=101.5, invalidation=98, prior_extreme=100,
        potential_score=20,
    )
    assert x.threat == Threat.LATE_CHASE
