from datetime import datetime
from zoneinfo import ZoneInfo

from dantex.session import intraday_session_status


IST = ZoneInfo("Asia/Kolkata")


def test_intraday_never_becomes_overnight():
    assert intraday_session_status(datetime(2026, 9, 21, 15, 20, tzinfo=IST)) == "force_exit"


def test_late_new_entries_are_blocked():
    assert intraday_session_status(datetime(2026, 9, 21, 15, 15, tzinfo=IST)) == "manage_only"
