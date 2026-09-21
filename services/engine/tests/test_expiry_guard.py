from dantex.expiry_guard import expiry_guard


def test_final_expiry_minutes_block_fresh_directional_entry():
    assert not expiry_guard(minutes_to_expiry=20).allowed


def test_near_expiry_demands_stronger_confirmation():
    assert expiry_guard(minutes_to_expiry=90).required_confirmation == 80
