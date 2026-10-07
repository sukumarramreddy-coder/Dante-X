from dantex.potential import potential_left


def test_spent_move_is_not_worth_chasing():
    p = potential_left(current=109, target=110, invalidation=105, estimated_cost_distance=0.2)
    assert not p.worthwhile


def test_asymmetric_move_has_potential():
    p = potential_left(current=101, target=110, invalidation=98, estimated_cost_distance=0.2)
    assert p.worthwhile
    assert p.score > 50
