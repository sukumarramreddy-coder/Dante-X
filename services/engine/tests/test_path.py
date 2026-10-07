from dantex.path import PathCheckpoint, evaluate_path


def test_path_requires_ordered_progress():
    checkpoints = [
        PathCheckpoint(100, "above"),
        PathCheckpoint(105, "above"),
        PathCheckpoint(110, "above"),
    ]
    p = evaluate_path(checkpoints, [99, 101, 103, 106])
    assert p.matched == 2
    assert p.score == 66.7
    assert p.next_level == 110
