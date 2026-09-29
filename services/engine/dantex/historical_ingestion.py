"""Append-only index history bootstrap; never live evidence or probability calibration."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from uuid import uuid4
from zoneinfo import ZoneInfo

from .providers.credentials import UpstoxCredentials
from .providers.upstox import UpstoxConfig
from .providers.upstox_rest import UpstoxRestClient

IST = ZoneInfo("Asia/Kolkata")
KEYS = {"NIFTY": "NSE_INDEX|Nifty 50", "BANKNIFTY": "NSE_INDEX|Nifty Bank"}
VERSION = "index-history-v1"


def candle_rows(payload):
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ValueError("Unsuccessful provider response")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("candles"), list):
        raise TypeError("Missing candle array")
    return data["candles"]


def normalize(row):
    if not isinstance(row, list) or len(row) not in (6, 7):
        raise ValueError("Invalid candle shape")
    stamp = datetime.fromisoformat(row[0])
    if stamp.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    stamp = stamp.astimezone(IST)
    values = row[1:]
    if any(isinstance(x, bool) or not isinstance(x, (int, float))
           or not math.isfinite(x) for x in values):
        raise ValueError("Non-finite candle value")
    opening, high, low, close, volume = values[:5]
    if min(opening, high, low, close) <= 0 or not low <= min(opening, close) <= max(opening, close) <= high:
        raise ValueError("Invalid OHLC geometry")
    if volume < 0 or (len(values) == 6 and values[5] < 0):
        raise ValueError("Negative volume or OI")
    return [stamp.isoformat(), *[float(x) for x in values[:5]],
            float(values[5]) if len(values) == 6 else None]


def safe_error(exc):
    # Do not persist provider response bodies, request URLs, or credentials.
    return f"HTTP_{exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__


class HistoryStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            # Prevent accidentally mixing the bootstrap into the live evidence DB.
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='validation_samples'").fetchone():
                raise ValueError("Use a separate history database, not the live validation database")
            db.execute("""CREATE TABLE IF NOT EXISTS historical_candles(
                instrument_key TEXT NOT NULL, ts TEXT NOT NULL, session_date TEXT NOT NULL,
                payload TEXT NOT NULL, ingested_at TEXT NOT NULL, source TEXT NOT NULL,
                PRIMARY KEY(instrument_key, ts))""")
            db.execute("""CREATE TABLE IF NOT EXISTS historical_import_events(
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
                payload TEXT NOT NULL)""")

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def event(self, run_id, payload):
        with self.connect() as db:
            db.execute("INSERT INTO historical_import_events(run_id,recorded_at,payload) VALUES(?,?,?)",
                       (run_id, datetime.now(IST).isoformat(), json.dumps(payload, sort_keys=True)))

    def ingest(self, key, rows):
        inserted = conflicts = 0
        with self.connect() as db:
            for row in rows:
                payload = json.dumps(row, separators=(",", ":"))
                old = db.execute("SELECT payload FROM historical_candles WHERE instrument_key=? AND ts=?",
                                 (key, row[0])).fetchone()
                if old:
                    conflicts += old[0] != payload
                    continue
                db.execute("INSERT INTO historical_candles VALUES(?,?,?,?,?,?)",
                           (key, row[0], row[0][:10], payload, datetime.now(IST).isoformat(),
                            "upstox:v3:minutes:1"))
                inserted += 1
        return inserted, conflicts


def ingest_sessions(client, store, *, sessions=90, end_date=None, now=None, pause=time.sleep):
    now = now or datetime.now(IST)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    # Exclude the current session even after close: daily history may still be settling.
    yesterday = now.astimezone(IST).date() - timedelta(days=1)
    end = end_date or yesterday
    if not 1 <= sessions <= 90 or end > yesterday:
        raise ValueError("Choose 1..90 sessions ending before today in IST")
    run_id = str(uuid4())
    report = {"run_id": run_id, "version": VERSION, "mode": "shadow",
              "scope": "INDEX_CANDLES_ONLY", "calibration_ready": False,
              "live_evidence_eligible": False, "probability": None,
              "requested_sessions": sessions, "end_date": end.isoformat(), "sessions": [],
              "missing_capabilities": ["historical_option_chains", "bid_ask_and_greeks",
                                       "full_evidence_replay", "outcome_labels", "walk_forward_validation"]}
    store.event(run_id, {"event": "STARTED", **report})
    start = end - timedelta(days=365)
    daily_dates = {}
    try:
        for symbol, key in KEYS.items():
            pause(0.4)
            raw = candle_rows(client.historical_candles(
                key, unit="days", interval=1, from_date=start.isoformat(), to_date=end.isoformat()))
            dates = {datetime.fromisoformat(normalize(row)[0]).date() for row in raw}
            daily_dates[symbol] = {d for d in dates if start <= d <= end}
    except Exception as exc:
        report.update(status="FAILED_DISCOVERY", error=safe_error(exc), selected_sessions=0)
        store.event(run_id, {"event": "FINISHED", **report})
        return report
    # Union avoids hiding a session merely because one instrument's daily bar is missing.
    selected = sorted(set().union(*daily_dates.values()))[-sessions:]
    report["selected_sessions"] = len(selected)
    abort = False
    for day in selected:
        for symbol, key in KEYS.items():
            item = {"date": day.isoformat(), "symbol": symbol, "inserted": 0,
                    "conflicts": 0, "daily_bar_present": day in daily_dates[symbol]}
            try:
                pause(0.4)
                raw = candle_rows(client.historical_candles(
                    key, unit="minutes", interval=1, from_date=day.isoformat(), to_date=day.isoformat()))
                unique = {}
                invalid = duplicate_conflicts = outside = 0
                for source in raw:
                    try:
                        row = normalize(source)
                        stamp = datetime.fromisoformat(row[0])
                        if stamp.date() != day or stamp.second or stamp.microsecond:
                            raise ValueError("Wrong session or interval")
                        minute = stamp.hour * 60 + stamp.minute
                        if not 555 <= minute < 930:
                            outside += 1
                            continue
                        if row[0] in unique and unique[row[0]] != row:
                            duplicate_conflicts += 1
                        else:
                            unique[row[0]] = row
                    except (ValueError, TypeError, OverflowError):
                        invalid += 1
                ordered = sorted(unique.values(), key=lambda r: r[0])
                inserted, conflicts = store.ingest(key, ordered)
                item.update(inserted=inserted, conflicts=conflicts + duplicate_conflicts,
                            accepted_minutes=len(ordered), missing_minutes=375-len(ordered),
                            invalid_rows=invalid, outside_regular_hours=outside,
                            first=ordered[0][0] if ordered else None,
                            last=ordered[-1][0] if ordered else None)
                complete = (len(ordered) == 375 and not invalid and not conflicts
                            and not duplicate_conflicts and not outside and item["daily_bar_present"])
                item["status"] = "COMPLETE_REGULAR_SESSION" if complete else "PARTIAL"
            except Exception as exc:
                item.update(status="FETCH_FAILED", error=safe_error(exc))
                abort = isinstance(exc, HTTPError) and exc.code in (401, 403, 429)
            report["sessions"].append(item)
            store.event(run_id, {"event": "SESSION", **item})
            if abort:
                break
        if abort:
            break
    complete_days = sum(all(any(i["date"] == d.isoformat() and i["symbol"] == s
                               and i["status"] == "COMPLETE_REGULAR_SESSION"
                               for i in report["sessions"]) for s in KEYS) for d in selected)
    report["complete_index_sessions"] = complete_days
    report["status"] = ("COMPLETE_INDEX_HISTORY" if complete_days == sessions else "PARTIAL")
    if abort:
        report["status"] = "BLOCKED_PROVIDER"
    store.event(run_id, {"event": "FINISHED", **report})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="Separate persistent history SQLite path")
    parser.add_argument("--sessions", type=int, default=90)
    parser.add_argument("--end-date", type=date.fromisoformat, help="Inclusive date; must precede today IST")
    args = parser.parse_args(argv)
    try:
        token = UpstoxCredentials.from_env().analytics_token
        client = UpstoxRestClient(UpstoxConfig(access_token=token))
        report = ingest_sessions(client, HistoryStore(args.db), sessions=args.sessions,
                                 end_date=args.end_date)
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "error": safe_error(exc),
                          "hint": "Check runtime analytics credential, date, and separate writable DB path",
                          "calibration_ready": False}))
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "COMPLETE_INDEX_HISTORY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
