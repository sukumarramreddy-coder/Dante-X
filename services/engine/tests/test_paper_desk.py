from datetime import datetime
from zoneinfo import ZoneInfo

from dantex.paper_desk import PaperDesk, mt5_shell

IST = ZoneInfo("Asia/Kolkata")


def test_kill_blocks_and_survives_new_handle(tmp_path):
    path = tmp_path / "paper.sqlite3"
    desk = PaperDesk(path)
    killed = desk.kill()
    assert killed["killed"] is True
    assert killed["position"] is None
    reopened = PaperDesk(path)
    decision = {
        "status": "DETECTED",
        "fresh_evidence": True,
        "direction": "CE",
        "reference_entry": 100,
        "reference_stop": 80,
        "reference_t1": 130,
    }
    result = reopened.consider(decision, now=datetime(2026, 10, 7, 10, 0, tzinfo=IST))
    assert result["action"] == "BLOCKED"
    assert result["reason"] == "kill_switch"
    assert result["live_orders"] is False


def test_prior_only_and_stale_do_not_fill(tmp_path):
    desk = PaperDesk(tmp_path / "paper.sqlite3")
    stale = desk.consider({"status": "DETECTED", "fresh_evidence": False, "reference_entry": 1, "reference_stop": 1, "reference_t1": 1})
    assert stale["action"] == "NO_TRADE"
    prior = desk.consider({
        "status": "PRIOR_ONLY",
        "fresh_evidence": True,
        "probability_status": "PRIOR_ONLY",
        "reference_entry": 100,
        "reference_stop": 80,
        "reference_t1": 130,
    })
    assert prior["action"] == "NO_TRADE"


def test_fresh_detected_fills_fake_position(tmp_path):
    desk = PaperDesk(tmp_path / "paper.sqlite3")
    result = desk.consider({
        "status": "DETECTED",
        "fresh_evidence": True,
        "direction": "PE",
        "reference_entry": 100,
        "reference_stop": 80,
        "reference_t1": 140,
    }, now=datetime(2026, 10, 5, 11, 0, tzinfo=IST))
    assert result["action"] == "FILL"
    assert result["money"] == "fake"
    assert result["position"]["qty"] == 1
    assert result["position"]["side"] == "PE"
    held = desk.consider({
        "status": "DETECTED",
        "fresh_evidence": True,
        "reference_entry": 100,
        "reference_stop": 80,
        "reference_t1": 140,
    })
    assert held["action"] == "HOLD"


def test_mt5_shell_cannot_wake():
    shell = mt5_shell()
    assert shell["state"] == "ASLEEP"
    assert shell["wake_allowed"] is False
    assert shell["order_client"] is None
    assert shell["live_orders"] is False
