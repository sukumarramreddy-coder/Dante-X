import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256

import pytest

from dantex.historical_ingestion import HistoryStore, IST, KEYS
from dantex.historical_replay import (ReplayClock, digest, label_index_path, load_session,
                                      new_store, run, source_connection)

START = datetime(2026, 9, 24, 9, 15, tzinfo=IST)


def row(i):
    return {'ts': (START+timedelta(minutes=i)).isoformat(), 'open': 100+i,
            'high': 102+i, 'low': 99+i, 'close': 101+i, 'volume': 0}


def advance(clock, i, missing=()):
    return clock.advance(START+timedelta(minutes=i),
                         {s: row(i) for s in KEYS if s not in missing})


def archive(tmp_path, count=375, missing=()):
    path = tmp_path/'source.sqlite3'
    store = HistoryStore(path)
    for symbol, key in KEYS.items():
        store.ingest(key, [list(row(i).values())+[None] for i in range(count)
                           if (symbol, i) not in missing])
    return path


def test_completed_session_aligned_bars_and_exact_ohlc():
    clock = ReplayClock()
    for i in range(375):
        record = advance(clock, i)
        assert record['known_at'] == (START+timedelta(minutes=i+1)).isoformat()
        windows = record['capture']['windows']['NIFTY']
        for n in (5, 15):
            assert len(windows[str(n)]) == min(60, (i+1)//n)
            for r in windows[str(n)]:
                start = datetime.fromisoformat(r['ts'])
                assert (start-START).total_seconds() % (n*60) == 0
                assert start+timedelta(minutes=n) <= datetime.fromisoformat(record['known_at'])
        if i == 4:
            assert windows['5'][0] == {'ts': row(0)['ts'], 'open': 100, 'high': 106,
                                       'low': 99, 'close': 105, 'volume': 0}


def test_prefix_equivalence_future_mutation_does_not_change_decisions():
    original, changed = ReplayClock(), ReplayClock()
    for i in range(100):
        before = advance(original, i)
        inputs = {s: row(i) for s in KEYS}
        if i >= 65:
            for r in inputs.values():
                for key in ('open', 'high', 'low', 'close'):
                    r[key] *= 100
        after = changed.advance(START+timedelta(minutes=i), inputs)
        if i < 65:
            assert before == after
        if i == 64:
            frozen = deepcopy(before)
    assert frozen['capture']['windows']['NIFTY']['1'][-1] == row(64)


def test_future_bar_and_reversed_clock_rejected():
    clock = ReplayClock()
    with pytest.raises(ValueError, match='Future'):
        clock.advance(START, {'NIFTY': row(1)})
    clock = ReplayClock()
    advance(clock, 1)
    with pytest.raises(ValueError, match='strictly'):
        advance(clock, 0)


def test_gap_clears_warmup_and_never_builds_partial_bucket():
    clock = ReplayClock()
    for i in range(30):
        record = advance(clock, i, ('NIFTY',) if i == 12 else ())
        if i == 14:
            assert record['capture']['windows']['NIFTY']['15'] == []
            assert record['capture']['windows']['NIFTY']['5'] == []
            assert len(record['capture']['windows']['BANKNIFTY']['15']) == 1
    assert len(record['capture']['windows']['NIFTY']['15']) == 1
    assert record['capture']['momentum']['NIFTY']['state'] == 'UNAVAILABLE'
    tomorrow = START+timedelta(days=1)
    next_row = {**row(0), 'ts': tomorrow.isoformat()}
    record = clock.advance(tomorrow, {s: next_row for s in KEYS})
    assert len(record['capture']['windows']['NIFTY']['1']) == 1
    assert record['capture']['windows']['NIFTY']['15'] == []


def test_labels_use_only_later_minutes_and_censor():
    clock = ReplayClock()
    for i in range(30):
        record = advance(clock, i)
    future = {START+timedelta(minutes=i): row(i) for i in range(375)}
    label = label_index_path(record, 'NIFTY', future, 15)
    assert label['delta_points'] == 15
    assert label['direction_agrees'] is True
    assert label['observations'] == 15
    future[START+timedelta(minutes=29)]['high'] = 999999
    assert label_index_path(record, 'NIFTY', future, 15) == label
    del future[START+timedelta(minutes=35)]
    assert label_index_path(record, 'NIFTY', future, 15)['status'] == 'CENSORED_MISSING_MINUTES'
    for i in range(30, 375):
        record = advance(clock, i)
    assert label_index_path(record, 'NIFTY', future, 15)['status'] == 'CENSORED_SESSION_END'


def test_source_read_only_output_exclusive_and_live_db_untouched(tmp_path):
    source = archive(tmp_path, count=2)
    before = source.read_bytes()
    db = source_connection(source)
    try:
        with pytest.raises(sqlite3.OperationalError):
            db.execute('DELETE FROM historical_candles')
    finally:
        db.close()
    with pytest.raises(FileExistsError):
        run(source, source)
    live = tmp_path/'live.sqlite3'
    with sqlite3.connect(live) as db:
        db.execute('CREATE TABLE validation_samples(id INTEGER)')
    old = live.read_bytes()
    with pytest.raises(FileExistsError):
        run(source, live)
    assert source.read_bytes() == before
    assert live.read_bytes() == old


def test_run_audit_repeatability_gates_and_durable_freeze(tmp_path, monkeypatch):
    source = archive(tmp_path)
    original = sha256(source.read_bytes()).hexdigest()
    output = tmp_path/'replay.sqlite3'
    import dantex.historical_replay as module
    labeler = module.label_index_path

    def checked(record, *args):
        with sqlite3.connect(output) as db:
            assert db.execute('SELECT count(*) FROM replay_decisions').fetchone()[0] == 375
            saved = json.loads(db.execute('SELECT payload FROM replay_decisions WHERE known_at=?',
                                         (record['known_at'],)).fetchone()[0])
            assert saved == record
        return labeler(record, *args)

    monkeypatch.setattr(module, 'label_index_path', checked)
    report = run(source, output)
    monkeypatch.setattr(module, 'label_index_path', labeler)
    again = run(source, tmp_path/'again.sqlite3')
    assert report == again
    assert report['decision_counts'] == {'NO_SETUP': 375}
    assert report['label_counts'] == {'COMPLETE': 720, 'CENSORED_SESSION_END': 30}
    assert sha256(source.read_bytes()).hexdigest() == original
    with sqlite3.connect(output) as db:
        chain = '0'*64
        for payload, value, previous in db.execute('SELECT payload,sha256,previous_sha256 FROM replay_decisions ORDER BY id'):
            record = json.loads(payload)
            assert previous == chain
            assert value == digest({'previous': chain, 'record': record})
            assert record['decision']['calibrated_probability'] is None
            assert record['decision']['authorization'] == 'NONE'
            assert not record['decision']['calibration_eligible']
            assert record['evidence_partition'] == 'historical_bootstrap'
            chain = value
        assert chain == report['decision_chain_sha256']
        assert db.execute('SELECT count(*) FROM replay_labels l JOIN replay_decisions d '
                          'ON d.id=l.decision_id WHERE l.prediction_sha256!=d.sha256').fetchone()[0] == 0
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='validation_samples'").fetchall()
        for table in ('replay_decisions', 'replay_labels', 'replay_events'):
            with pytest.raises(sqlite3.IntegrityError, match='immutable'):
                db.execute(f'DELETE FROM {table}')
            with pytest.raises(sqlite3.IntegrityError, match='immutable'):
                db.execute(f"UPDATE {table} SET payload='{{}}'")


def test_partial_coverage_and_missing_symbol(tmp_path):
    source = archive(tmp_path, count=50, missing=(('BANKNIFTY', 30),))
    report = run(source, tmp_path/'partial.sqlite3')
    assert report['status'] == 'PARTIAL'
    assert report['complete_index_sessions'] == 0
    assert report['coverage'][0]['symbols']['BANKNIFTY']['missing_minutes'] == 326
    assert report['label_counts']['CENSORED_MISSING_MINUTES'] > 0


@pytest.mark.parametrize('mutation', ["source='wrong'", "ts='2026-09-24T09:15:01+05:30'",
                                    "payload='[\"2026-09-24T09:15:00+05:30\",100,90,99,101,0]' "])
def test_malformed_archive_rejected(tmp_path, mutation):
    source = archive(tmp_path, count=1)
    with sqlite3.connect(source) as db:
        db.execute(f'UPDATE historical_candles SET {mutation}')
    db = source_connection(source)
    try:
        with pytest.raises(ValueError):
            load_session(db, '2026-09-24')
    finally:
        db.close()


def test_failed_run_never_reports_finished(tmp_path):
    source = archive(tmp_path, count=1)
    with sqlite3.connect(source) as db:
        db.execute("UPDATE historical_candles SET source='wrong'")
    output = tmp_path/'failed.sqlite3'
    with pytest.raises(ValueError):
        run(source, output)
    with sqlite3.connect(output) as db:
        assert [json.loads(r[0])['event'] for r in db.execute('SELECT payload FROM replay_events')] == ['STARTED', 'FAILED']


def test_existing_backup_and_hardlink_rejected(tmp_path):
    source = archive(tmp_path, count=1)
    alias = tmp_path/'alias.sqlite3'
    alias.hardlink_to(source)
    with pytest.raises(FileExistsError):
        new_store(alias)


def test_full_pipeline_future_archive_mutation_preserves_frozen_prefix(tmp_path, monkeypatch):
    import socket

    def blocked(*args, **kwargs):
        raise AssertionError('Offline replay attempted network access')

    monkeypatch.setattr(socket, 'socket', blocked)
    source = archive(tmp_path, count=100)
    first = tmp_path/'first.sqlite3'
    second = tmp_path/'second.sqlite3'
    run(source, first)
    with sqlite3.connect(source) as db:
        for key, ts, payload in db.execute('SELECT instrument_key,ts,payload FROM historical_candles').fetchall():
            if datetime.fromisoformat(ts) >= START+timedelta(minutes=65):
                row = json.loads(payload)
                row[1:5] = [x*10 for x in row[1:5]]
                db.execute('UPDATE historical_candles SET payload=? WHERE instrument_key=? AND ts=?',
                           (json.dumps(row), key, ts))
    run(source, second)
    with sqlite3.connect(first) as a, sqlite3.connect(second) as b:
        query = 'SELECT payload,sha256 FROM replay_decisions WHERE id<=65 ORDER BY id'
        assert a.execute(query).fetchall() == b.execute(query).fetchall()
        query = "SELECT payload FROM replay_labels WHERE decision_id=65 AND symbol='NIFTY'"
        assert a.execute(query).fetchone() != b.execute(query).fetchone()


@pytest.mark.parametrize('state,delta,agrees', [('PE', -5, True), ('PE', 5, False),
                                             ('CE', -5, False), ('NEUTRAL', 0, None)])
def test_direction_label_semantics(state, delta, agrees):
    record = advance(ReplayClock(), 0)
    record['capture']['momentum']['NIFTY']['state'] = state
    future = {START+timedelta(minutes=1): {**row(1), 'close': 101+delta}}
    label = label_index_path(record, 'NIFTY', future, 1)
    assert label['direction_agrees'] is agrees
    assert label['direction_label'] == ('UP' if delta > 0 else 'DOWN' if delta < 0 else 'FLAT')
