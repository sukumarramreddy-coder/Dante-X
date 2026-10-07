from copy import deepcopy
from datetime import datetime, timedelta
import json
import sqlite3

import pytest

from dantex.historical_ingestion import HistoryStore, IST, KEYS
from dantex.historical_replay import decide, forward_label, load_archive, run_replay, temporal_blocks


def rows(n=375):
    start = datetime(2026, 5, 20, 9, 15, tzinfo=IST)
    return [[(start + timedelta(minutes=i)).isoformat(), 100+i, 102+i, 99+i, 101+i, 0, None] for i in range(n)]


def test_future_mutation_cannot_change_decision_prefix():
    source = rows(50)
    cutoff = datetime.fromisoformat(source[24][0]) + timedelta(minutes=1)
    original = decide('NIFTY', source[:25], cutoff)
    changed = deepcopy(source)
    for row in changed[25:]:
        row[1:5] = [1, 10000, 1, 9999]
    assert decide('NIFTY', changed[:25], cutoff) == original
    assert original['decision']['authorization'] == 'NONE'
    assert original['probability'] is None
    assert not original['calibration_ready']


def test_unclosed_duplicate_and_out_of_order_prefixes_rejected():
    source = rows(25)
    cutoff = datetime.fromisoformat(source[-1][0]) + timedelta(minutes=1)
    with pytest.raises(ValueError, match='future'):
        decide('NIFTY', source, cutoff - timedelta(seconds=1))
    for invalid in (source[::-1], source + [source[-1]], source[:5] + source[6:]):
        with pytest.raises(ValueError):
            decide('NIFTY', invalid, cutoff)


def test_labels_use_next_open_and_never_decision_bar_or_next_session():
    source = rows(50)
    cutoff = datetime.fromisoformat(source[24][0]) + timedelta(minutes=1)
    event = decide('NIFTY', source[:25], cutoff)
    label = forward_label(event, source[25:], 5)
    assert label['entry_reference'] == 125
    assert label['exit_reference'] == 130
    assert label['available_at'] == (cutoff + timedelta(minutes=5)).isoformat()
    assert label['index_move_bps'] == pytest.approx(400)
    assert label['hypothetical_round_trip_cost_bps']['5'] == pytest.approx(395)
    assert not label['trade_outcome']
    with pytest.raises(ValueError):
        forward_label(event, source[24:], 5)
    assert forward_label(event, source[-2:], 5)['status'] == 'CENSORED'


def test_fixed_temporal_blocks_do_not_train_or_shuffle():
    days = [str(i) for i in range(90)]
    blocks = temporal_blocks(days)
    assert [blocks[days[i]] for i in (0, 29, 30, 49, 50, 69, 70, 89)] == [
        'development', 'development', 'holdout_1', 'holdout_1',
        'holdout_2', 'holdout_2', 'holdout_3', 'holdout_3']


def make_archive(path):
    store = HistoryStore(path)
    for key in KEYS.values():
        store.ingest(key, rows())
    return store


def test_missing_counterpart_quarantines_whole_session(tmp_path):
    store = HistoryStore(tmp_path / 'archive.db')
    store.ingest(KEYS['NIFTY'], rows())
    sessions, rejected = load_archive(tmp_path / 'archive.db')
    assert not sessions
    assert '2026-05-20' in rejected


def test_mixed_store_and_source_mismatch_rejected(tmp_path):
    path = tmp_path / 'archive.db'
    make_archive(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE historical_candles SET source='synthetic' WHERE instrument_key=?", (KEYS['NIFTY'],))
    assert not load_archive(path)[0]
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE validation_samples(id INTEGER)')
    with pytest.raises(ValueError, match='separate'):
        load_archive(path)


def test_replay_is_read_only_and_preserves_rejections_and_censoring(tmp_path):
    path = tmp_path / 'archive.db'
    make_archive(path)
    before = path.read_bytes()
    report = run_replay(path, tmp_path / 'run')
    assert path.read_bytes() == before
    assert report['decision_counts'] == {'NO_SETUP': 750}
    assert report['summary']['development:NIFTY:30m']['censored'] == 30
    assert report['summary']['development:NIFTY:30m']['observed'] == 345
    assert not report['calibration_ready']
    assert json.loads((tmp_path / 'run/report.json').read_text())['source_unchanged']
    with pytest.raises(ValueError, match='preserve'):
        run_replay(path, tmp_path / 'run')
