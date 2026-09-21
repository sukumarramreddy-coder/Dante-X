import pytest

from dantex.decision_lock import LockedTrigger, revise_trigger


def test_armed_trigger_cannot_be_moved():
    with pytest.raises(ValueError):
        revise_trigger(LockedTrigger("x", 101), new_trigger=102, cancelled=False, fresh_evidence=True)


def test_cancelled_setup_can_create_auditable_revision():
    x = revise_trigger(LockedTrigger("x", 101), new_trigger=102, cancelled=True, fresh_evidence=True)
    assert x.trigger == 102
    assert x.revision == 2
