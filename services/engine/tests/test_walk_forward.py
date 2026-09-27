from copy import deepcopy
from datetime import datetime, timedelta
import json
import shutil
import sqlite3

import pytest

from dantex.historical_ingestion import IST, KEYS
from dantex.historical_replay import VERSION as REPLAY_VERSION, digest, encoded, new_store
from dantex.knowledge_policy import KT_VERSION
from dantex.walk_forward import (RULES, build_plan, evaluate, freeze_plan, manifest,
                                 partition_samples, source_connection, summarize, verified_samples)


@pytest.fixture(scope='module')
def replay_fixture(tmp_path_factory):
    path = tmp_path_factory.mktemp('walk-forward')/'replay.sqlite3'
    days = [(datetime(2026, 1, 1, tzinfo=IST)+timedelta(days=i)).date().isoformat() for i in range(10)]
    metadata = {'event': 'STARTED', 'version': REPLAY_VERSION, 'kt_version': KT_VERSION,
                'sessions': days, 'horizon_minutes': 15, 'engine_source_sha256': 'fixture-engine',
                'evidence_partition': 'historical_bootstrap', 'calibrated_probability': None,
                'calibration_eligible': False, 'execution_enabled': False}
    db = new_store(path)
    db.execute('INSERT INTO replay_events(payload) VALUES(?)', (encoded(metadata),))
    chain = '0'*64
    for d, day in enumerate(days):
        opening = datetime.fromisoformat(day+'T09:16:00+05:30')
        for minute in range(375):
            at = opening+timedelta(minutes=minute)
            direction = 'CE' if minute % 2 == 0 else 'PE'
            record = {'version': REPLAY_VERSION, 'kt_version': KT_VERSION,
                      'known_at': at.isoformat(), 'bar_start': (at-timedelta(minutes=1)).isoformat(),
                      'evidence_partition': 'historical_bootstrap',
                      'decision': {'status': 'NO_SETUP', 'operator_action': 'WAIT', 'authorization': 'NONE',
                                   'calibrated_probability': None, 'probability': None,
                                   'calibration_eligible': False, 'live_evidence_eligible': False},
                      'capture': {'engine_source_sha256': 'fixture-engine',
                                  'momentum': {s: {'state': direction} for s in KEYS},
                                  'windows': {s: {'1': [{'ts': (at-timedelta(minutes=1)).isoformat(),
                                                        'close': 100}]} for s in KEYS}}}
            value = digest({'previous': chain, 'record': record})
            rid = db.execute('INSERT INTO replay_decisions(known_at,payload,sha256,previous_sha256) '
                             'VALUES(?,?,?,?)', (at.isoformat(), encoded(record), value, chain)).lastrowid
            chain = value
            for symbol in KEYS:
                label = {'kind': 'INDEX_FORWARD_MOVE', 'horizon_minutes': 15,
                         'component_direction': direction, 'calibration_eligible': False,
                         'trade_outcome_eligible': False, 'status': 'CENSORED_SESSION_END'}
                if minute < 360:
                    delta = 1 if d % 2 == 0 else -1
                    label.update(status='COMPLETE', end_at=(at+timedelta(minutes=15)).isoformat(),
                                 observations=15, reference_close=100, delta_points=delta,
                                 return_bps=delta*100, max_up_points=2, max_down_points=-2,
                                 direction_label='UP' if delta > 0 else 'DOWN',
                                 direction_agrees=(delta > 0 if direction == 'CE' else delta < 0))
                db.execute('INSERT INTO replay_labels VALUES(?,?,?,?)', (rid, symbol, encoded(label), value))
    finished = {**metadata, 'event': 'FINISHED', 'status': 'COMPLETE',
                'complete_index_sessions': len(days), 'decision_chain_sha256': chain,
                'source_rows_sha256': 'fixture-source', 'decision_counts': {'NO_SETUP': 3750},
                'label_counts': {'COMPLETE': 7200, 'CENSORED_SESSION_END': 300},
                'coverage': [{'date': day, 'symbols': {s: {'complete': True, 'accepted_minutes': 375,
                                                           'missing_minutes': 0} for s in KEYS}}
                             for day in days]}
    db.execute('INSERT INTO replay_events(payload) VALUES(?)', (encoded(finished),))
    db.commit()
    db.close()
    return path


def plan_for(source, tmp_path):
    path = tmp_path/'plan.json'
    return freeze_plan(source, path, initial=2, test=2, holdout=2, embargo=1), path


def test_disjoint_expanding_context_gaps_and_final_holdout(replay_fixture, tmp_path):
    plan, _ = plan_for(replay_fixture, tmp_path)
    days = plan['sessions']
    assert [f['evaluation_sessions'] for f in plan['folds']] == [days[3:5], days[5:7], days[8:]]
    used = set()
    for fold in plan['folds']:
        context, gap, test = map(set, (fold['context_sessions'], fold['embargo_sessions'], fold['evaluation_sessions']))
        assert not context & test and not gap & test and not gap & context
        assert max(context) < min(gap) < min(test)
        assert not used & test
        used |= test
    assert plan['rules'] == RULES


def test_90_session_default_split_and_partial_final_fold():
    metadata = {'sessions': [(datetime(2026, 1, 1, tzinfo=IST)+timedelta(days=i)).date().isoformat() for i in range(90)],
                'horizon_minutes': 15, 'decision_chain_sha256': 'a', 'source_rows_sha256': 'b',
                'engine_source_sha256': 'c'}
    plan = build_plan(metadata)
    assert [len(f['evaluation_sessions']) for f in plan['folds']] == [10, 10, 10, 8, 20]
    assert len(plan['folds'][0]['context_sessions']) == 30


@pytest.mark.parametrize('config', [{'initial': 0}, {'test': -1}, {'holdout': True},
                                   {'embargo': -1}, {'initial': 9}])
def test_invalid_or_insufficient_plan_rejected(replay_fixture, config):
    db = source_connection(replay_fixture)
    try:
        with pytest.raises(ValueError):
            build_plan(manifest(db), **{'initial': 2, 'test': 2, 'holdout': 2, 'embargo': 1, **config})
    finally:
        db.close()


def test_deterministic_readonly_evaluation_and_no_promotion(replay_fixture, tmp_path, monkeypatch):
    import socket

    def no_network(*args, **kwargs):
        raise AssertionError('Network access')

    monkeypatch.setattr(socket, 'socket', no_network)
    before = replay_fixture.read_bytes()
    plan, path = plan_for(replay_fixture, tmp_path)
    report = evaluate(replay_fixture, path, tmp_path/'report.json')
    again = evaluate(replay_fixture, path, tmp_path/'again.json')
    assert report == again
    assert replay_fixture.read_bytes() == before
    assert report['calibrated_probability'] is None
    assert report['calibration_eligible'] is False
    assert report['execution_enabled'] is False
    assert report['evidence_partition'] == 'historical_bootstrap'
    assert report['plan_sha256'] == plan['plan_sha256']
    assert 'directional' not in report['all_session_coverage']['NIFTY']
    assert len(report['walk_forward_stability']['NIFTY_CE']) == 2
    for fold in report['folds']:
        assert fold['evaluation_purged'] == 30
        assert fold['context_purged'] == 30
        for group in fold['metrics']['NIFTY']['directional'].values():
            assert group['samples'] == 24
            assert group['agreement_rate'] == 0.5
            assert group['agreed'] == group['disagreed_including_flat'] == 12
            assert group['session_min_agreement_rate'] == 0
            assert group['session_max_agreement_rate'] == 1
    with pytest.raises(FileExistsError):
        evaluate(replay_fixture, path, tmp_path/'report.json')


def test_purging_uses_label_end_not_decision_time():
    day = '2026-01-01'
    at = datetime(2026, 1, 1, 15, 20, tzinfo=IST)
    base = {'day': day, 'known_at': at}
    rows = [{**base, 'end_at': at+timedelta(minutes=10)},
            {**base, 'end_at': at+timedelta(minutes=11)}]
    kept, purged = partition_samples(rows, [day])
    assert kept == rows[:1] and purged == 1


def test_fixed_grid_does_not_cherry_pick_labels_or_direction(replay_fixture):
    db = source_connection(replay_fixture)
    try:
        rows = list(verified_samples(db, manifest(db)))
    finally:
        db.close()
    selected = [s for s in rows if s['grid'] and s['symbol'] == 'NIFTY']
    for left, right in zip(selected, selected[1:]):
        assert right['known_at']-left['known_at'] >= timedelta(minutes=15)
    summary = summarize(rows[:750], ['2026-01-01'])
    assert summary['NIFTY']['scheduled_grid_observations'] == 25
    assert summary['NIFTY']['complete_grid_observations'] == 24
    mutated = deepcopy(rows[:750])
    for s in mutated:
        s['direction'] = 'UNAVAILABLE'
    alternate = summarize(mutated, ['2026-01-01'])
    assert alternate['NIFTY']['scheduled_grid_observations'] == 25
    assert alternate['NIFTY']['directional']['CE']['agreement_rate'] is None


def test_changed_plan_rejected(replay_fixture, tmp_path):
    plan, path = plan_for(replay_fixture, tmp_path)
    plan['folds'][0]['evaluation_sessions'].reverse()
    path.write_text(encoded(plan))
    with pytest.raises(ValueError, match='Plan changed'):
        evaluate(replay_fixture, path, tmp_path/'bad.json')
    assert not (tmp_path/'bad.json').exists()


def mutable_copy(source, tmp_path):
    target = tmp_path/'mutable.sqlite3'
    shutil.copyfile(source, target)
    with sqlite3.connect(target) as db:
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
            db.execute(f'DROP TRIGGER {name}')
    return target


def test_label_tampering_after_plan_rejected(replay_fixture, tmp_path):
    target = mutable_copy(replay_fixture, tmp_path)
    _, path = plan_for(target, tmp_path)
    with sqlite3.connect(target) as db:
        db.execute("UPDATE replay_labels SET payload='{}' WHERE decision_id=1")
    with pytest.raises(ValueError, match='identity mismatch'):
        evaluate(target, path, tmp_path/'bad.json')


def test_frozen_prediction_tampering_rejected(replay_fixture, tmp_path):
    target = mutable_copy(replay_fixture, tmp_path)
    _, path = plan_for(target, tmp_path)
    with sqlite3.connect(target) as db:
        db.execute("UPDATE replay_decisions SET payload='{}' WHERE id=1")
    with pytest.raises(ValueError, match='audit chain'):
        evaluate(target, path, tmp_path/'bad.json')


@pytest.mark.parametrize('change', ['missing_label', 'bad_horizon', 'nonfinite', 'future_reference'])
def test_invalid_input_even_when_bound_in_new_plan(replay_fixture, tmp_path, change):
    target = mutable_copy(replay_fixture, tmp_path)
    with sqlite3.connect(target) as db:
        if change == 'missing_label':
            db.execute('DELETE FROM replay_labels WHERE decision_id=1')
        else:
            label = json.loads(db.execute("SELECT payload FROM replay_labels WHERE decision_id=1 AND symbol='NIFTY'").fetchone()[0])
            if change == 'bad_horizon':
                label['end_at'] = '2026-01-01T09:30:00+05:30'
            elif change == 'nonfinite':
                label['return_bps'] = float('nan')
            else:
                label['reference_close'] = 200
                label['return_bps'] = label['delta_points']/200*10000
            db.execute("UPDATE replay_labels SET payload=? WHERE decision_id=1 AND symbol='NIFTY'", (json.dumps(label),))
    _, path = plan_for(target, tmp_path)
    with pytest.raises(ValueError):
        evaluate(target, path, tmp_path/'bad.json')


def test_partial_or_failed_run_rejected(replay_fixture, tmp_path):
    target = mutable_copy(replay_fixture, tmp_path)
    with sqlite3.connect(target) as db:
        db.execute("INSERT INTO replay_events(payload) VALUES('{\"event\":\"FAILED\"}')")
    with pytest.raises(ValueError, match='finished'):
        plan_for(target, tmp_path)


def test_future_holdout_outcomes_cannot_change_earlier_metrics(replay_fixture, tmp_path):
    plan, path = plan_for(replay_fixture, tmp_path)
    original = evaluate(replay_fixture, path, tmp_path/'original.json')
    target = mutable_copy(replay_fixture, tmp_path)
    with sqlite3.connect(target) as db:
        for rid, symbol, payload in db.execute('SELECT decision_id,symbol,payload FROM replay_labels WHERE decision_id>3000').fetchall():
            label = json.loads(payload)
            if label['status'] == 'COMPLETE':
                label.update(delta_points=2, return_bps=200, direction_label='UP',
                             direction_agrees=label['component_direction'] == 'CE')
                db.execute('UPDATE replay_labels SET payload=? WHERE decision_id=? AND symbol=?',
                           (encoded(label), rid, symbol))
    alternate_path = tmp_path/'alternative-plan.json'
    alternate = freeze_plan(target, alternate_path, **plan['config'])
    assert alternate['folds'] == plan['folds']
    changed = evaluate(target, alternate_path, tmp_path/'changed.json')
    assert changed['folds'][:-1] == original['folds'][:-1]
    assert changed['folds'][-1]['metrics'] != original['folds'][-1]['metrics']
