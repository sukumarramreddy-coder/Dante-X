from dantex.radar import RadarInputs
from dantex.ranking import RadarCandidate, rank_candidates


def test_blocked_candidate_never_wins_radar():
    strong_but_blocked = RadarCandidate(
        "A", "index_option", "bullish",
        RadarInputs(95, 95, 95, 3, 95, 95), False, "illiquid"
    )
    modest = RadarCandidate(
        "B", "equity", "bullish",
        RadarInputs(65, 65, 70, 1.8, 80, 80), True
    )
    ranked = rank_candidates([strong_but_blocked, modest])
    assert ranked[0].symbol == "B"
    assert ranked[1].status == "blocked"
