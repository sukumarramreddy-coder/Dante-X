import json
import sqlite3
from datetime import date, datetime, timedelta
from urllib.error import HTTPError

import pytest

from dantex.historical_ingestion import HistoryStore, IST, ingest_sessions, normalize

NOW = datetime(2026, 9, 25, 17, tzinfo=IST)
DAY = date(2026, 9, 24)


def bars(day=DAY, count=375):
    start = datetime.combine(day, datetime.min.time(), IST) + timedelta(hours=9, minutes=15)
    return [[(start + timedelta(minutes=i)).isoformat(), 100, 102, 99, 101, 0, 0]
            for i in range(count)]


class Provider:
    def __init__(self, days=None, minute_rows=None):
        self.days = days or [DAY]
        self.minute_rows = minute_rows
        self.calls = []

    def historical_candles(self, key, **args):
        self.calls.append((key, args))
        if args['unit'] == 'days':
            rows = [bars(d, 1)[0] for d in self.days]
        else:
            rows = self.minute_rows
            if isinstance(rows, Exception):
                raise rows
            if rows is None:
                rows = bars(date.fromisoformat(args['from_date']))
        return {'status': 'success', 'data': {'candles': rows}}


def run(tmp_path, provider, **kwargs):
    store = HistoryStore(tmp_path / 'history.sqlite3')
    return ingest_sessions(provider, store, now=NOW, pause=lambda _: None, **kwargs), store


def test_complete_idempotent_preserves_existing_evidence(tmp_path):
    report, store = run(tmp_path, Provider(), sessions=1)
    assert report['status'] == 'COMPLETE_INDEX_HISTORY'
    assert report['complete_index_sessions'] == 1
    assert not report['calibration_ready'] and not report['live_evidence_eligible']
    assert report['probability'] is None
    with store.connect() as db:
        before = db.execute('SELECT * FROM historical_candles ORDER BY instrument_key,ts').fetchall()
    second = ingest_sessions(Provider(), store, sessions=1, now=NOW, pause=lambda _: None)
    assert sum(s['inserted'] for s in second['sessions']) == 0
    with store.connect() as db:
        assert before == db.execute('SELECT * FROM historical_candles ORDER BY instrument_key,ts').fetchall()
    assert len(before) == 750


def test_provider_dates_not_weekdays_include_special_weekend(tmp_path):
    dates = [date(2026, 9, 19), date(2026, 9, 22), DAY, NOW.date()]
    provider = Provider(days=dates)
    report, _ = run(tmp_path, provider, sessions=3)
    assert sorted({s['date'] for s in report['sessions']}) == [d.isoformat() for d in dates[:3]]
    assert all(a['from_date'] == a['to_date'] for _, a in provider.calls if a['unit'] == 'minutes')


def test_short_history_does_not_claim_90_sessions(tmp_path):
    report, _ = run(tmp_path, Provider(), sessions=90)
    assert report['selected_sessions'] == 1
    assert report['status'] == 'PARTIAL'


def test_90_distinct_provider_sessions_selected(tmp_path):
    dates = [DAY - timedelta(days=i) for i in range(100)]
    report, _ = run(tmp_path, Provider(days=dates, minute_rows=[]), sessions=90)
    assert report['selected_sessions'] == 90
    assert len(report['sessions']) == 180
    assert min(s['date'] for s in report['sessions']) == (DAY-timedelta(days=89)).isoformat()


def test_holes_duplicates_invalid_and_outside_hours_are_not_complete(tmp_path):
    rows = bars()
    rows.pop(100)
    rows += [rows[0], [DAY.isoformat()+'T09:15:00', 100, 102, 99, 101, 0],
             [DAY.isoformat()+'T16:00:00+05:30', 100, 102, 99, 101, 0]]
    report, _ = run(tmp_path, Provider(minute_rows=rows), sessions=1)
    assert report['status'] == 'PARTIAL'
    item = report['sessions'][0]
    assert item['missing_minutes'] == 1
    assert item['invalid_rows'] == 1 and item['outside_regular_hours'] == 1


def test_revised_prices_never_replace_originals(tmp_path):
    _, store = run(tmp_path, Provider(), sessions=1)
    rows = bars()
    rows[0][4] = 100
    report = ingest_sessions(Provider(minute_rows=rows), store, sessions=1, now=NOW, pause=lambda _: None)
    assert report['status'] == 'PARTIAL'
    assert report['sessions'][0]['conflicts'] == 1
    with store.connect() as db:
        saved = json.loads(db.execute('SELECT payload FROM historical_candles ORDER BY ts LIMIT 1').fetchone()[0])
    assert saved[4] == 101


def test_wrong_date_and_duplicate_conflicts_flagged(tmp_path):
    rows = bars()
    changed = rows[0].copy()
    changed[4] = 100
    report, _ = run(tmp_path, Provider(minute_rows=rows+[changed]+bars(DAY-timedelta(days=1), 1)), sessions=1)
    assert report['sessions'][0]['conflicts'] == 1
    assert report['sessions'][0]['invalid_rows'] == 1
    assert report['status'] == 'PARTIAL'


@pytest.mark.parametrize('code', [401, 403, 429])
def test_auth_and_rate_limit_abort_without_leaking_secrets(tmp_path, code):
    provider = Provider(minute_rows=HTTPError('https://secret.invalid', code, 'secret', {}, None))
    report, _ = run(tmp_path, provider, sessions=1)
    assert report['status'] == 'BLOCKED_PROVIDER'
    assert len(provider.calls) == 3
    assert 'secret' not in json.dumps(report)


def test_discovery_failure_does_not_invent_sessions(tmp_path):
    class Bad(Provider):
        def historical_candles(self, key, **args):
            return {'status': 'error', 'data': {'candles': []}}
    report, _ = run(tmp_path, Bad(), sessions=90)
    assert report['status'] == 'FAILED_DISCOVERY'
    assert report['sessions'] == []


def test_missing_daily_bar_does_not_hide_date(tmp_path):
    class Missing(Provider):
        def historical_candles(self, key, **args):
            if 'Bank' in key and args['unit'] == 'days':
                return {'status': 'success', 'data': {'candles': []}}
            return super().historical_candles(key, **args)
    report, _ = run(tmp_path, Missing(), sessions=1)
    assert report['selected_sessions'] == 1 and report['status'] == 'PARTIAL'


def test_refuses_live_validation_database(tmp_path):
    path = tmp_path/'live.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE validation_samples(id INTEGER)')
        db.execute('INSERT INTO validation_samples VALUES(42)')
    with pytest.raises(ValueError):
        HistoryStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT * FROM validation_samples').fetchall() == [(42,)]


@pytest.mark.parametrize('sessions,end', [(0, DAY), (91, DAY), (1, NOW.date())])
def test_invalid_bounds_make_no_provider_calls(tmp_path, sessions, end):
    provider = Provider()
    with pytest.raises(ValueError):
        run(tmp_path, provider, sessions=sessions, end_date=end)
    assert provider.calls == []


@pytest.mark.parametrize('value', [float('nan'), float('inf'), True, -1])
def test_rejects_invalid_price(value):
    row = bars(count=1)[0]
    row[1] = value
    with pytest.raises(ValueError):
        normalize(row)
