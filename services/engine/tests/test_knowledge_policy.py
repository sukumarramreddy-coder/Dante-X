from dantex.knowledge_policy import (
    CALIBRATION_STAGES,
    FROZEN_POLICY,
    KT_VERSION,
    OperatorAction,
    REVIEW_SESSION_CHECKPOINTS,
)


def test_frozen_kt_keeps_phase_one_read_only_and_non_adaptive():
    assert KT_VERSION == "1.0-frozen"
    assert FROZEN_POLICY.read_only
    assert not FROZEN_POLICY.execution_enabled
    assert not FROZEN_POLICY.self_adaptation_during_initial_calibration


def test_frozen_kt_preserves_core_reasoning_boundaries():
    assert FROZEN_POLICY.maintain_competing_sides
    assert FROZEN_POLICY.separate_direction_from_instrument
    assert FROZEN_POLICY.structural_invalidation_before_quantity
    assert FROZEN_POLICY.net_risk_reward_required
    assert FROZEN_POLICY.intraday_must_exit_same_day
    assert FROZEN_POLICY.preserve_failures
    assert FROZEN_POLICY.preserve_rejected_setups


def test_probability_requires_real_validation():
    assert FROZEN_POLICY.calibrated_probability_requires_validation
    assert not FROZEN_POLICY.synthetic_evidence_may_unlock_calibration
    assert REVIEW_SESSION_CHECKPOINTS == (30, 60, 90)
    assert CALIBRATION_STAGES[-1] == "calibration_gate"


def test_operator_vocabulary_is_stable():
    assert tuple(action.value for action in OperatorAction) == (
        "WAIT", "GO", "HOLD", "PROTECT", "EXIT"
    )
