"""Frozen-rule historical walk-forward diagnostics; never calibration or trading."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from statistics import mean

from .historical_ingestion import IST, KEYS
from .historical_replay import VERSION as REPLAY_VERSION, digest, encoded, source_connection
from .knowledge_policy import KT_VERSION

VERSION = 'historical-walk-forward-v1'
RULES = {
    'strategy': 'FROZEN_NO_FITTING', 'sampling': 'SESSION_0916_FIXED_HORIZON_GRID',
    'purge': 'LABEL_END_MUST_BE_WITHIN_PARTITION',
    'metric': 'MOMENTUM_DIRECTION_AGREEMENT_NOT_TRADE_WIN_RATE',
    'evidence_partition': 'historical_bootstrap', 'calibration_eligible': False,
    'calibrated_probability': None, 'execution_enabled': False,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stamp(value):
    at = datetime.fromisoformat(value)
    require(at.tzinfo is not None, 'Naive timestamp')
    return at.astimezone(IST)


def manifest(db):
    events = [json.loads(r[0]) for r in db.execute('SELECT payload FROM replay_events ORDER BY id')]
    require(len(events) == 2 and events[0]['event'] == 'STARTED'
            and events[-1]['event'] == 'FINISHED', 'Replay not successfully finished')
    result = events[-1]
    require(result['version'] == REPLAY_VERSION and result['kt_version'] == KT_VERSION,
            'Unsupported replay or KT version')
    require(result['status'] == 'COMPLETE', 'Complete two-index sessions required')
    require(result['evidence_partition'] == 'historical_bootstrap'
            and result['calibration_eligible'] is False
            and result['calibrated_probability'] is None and result['execution_enabled'] is False,
            'Replay safety partition invalid')
    days = result['sessions']
    require(days and days == sorted(set(days)), 'Unordered or duplicate sessions')
    for day in days:
        require(date.fromisoformat(day).isoformat() == day, 'Invalid session date')
    require(isinstance(result['horizon_minutes'], int) and 1 <= result['horizon_minutes'] <= 375,
            'Invalid horizon')
    for key in ('version', 'kt_version', 'sessions', 'engine_source_sha256', 'horizon_minutes'):
        require(result[key] == events[0][key], 'Replay metadata changed')
    require(result['complete_index_sessions'] == len(days), 'Incomplete source coverage')
    coverage = result['coverage']
    require([c['date'] for c in coverage] == days, 'Coverage/session mismatch')
    require(all(set(c['symbols']) == set(KEYS) and all(
        s['complete'] is True and s['accepted_minutes'] == 375 and s['missing_minutes'] == 0
        for s in c['symbols'].values()) for c in coverage), 'Incomplete source coverage')
    return result


def labels_digest(db):
    """Bind label bytes without inspecting outcomes or computing performance."""
    result = sha256()
    for row in db.execute('SELECT decision_id,symbol,payload,prediction_sha256 '
                          'FROM replay_labels ORDER BY decision_id,symbol'):
        result.update(encoded(list(row)).encode())
        result.update(b'\n')
    return result.hexdigest()


def build_plan(metadata, *, initial=30, test=10, holdout=20, embargo=1):
    for name, value in (('initial', initial), ('test', test), ('holdout', holdout), ('embargo', embargo)):
        require(type(value) is int and value >= (0 if name == 'embargo' else 1),
                f'Invalid {name} session count')
    days = metadata['sessions']
    limit = len(days)-holdout-embargo
    require(initial+embargo < limit, 'Insufficient sessions for development, test, gaps and holdout')
    folds = []
    for start in range(initial+embargo, limit, test):
        folds.append({'name': f'fold_{len(folds)+1}', 'kind': 'WALK_FORWARD',
                      'context_sessions': days[:start-embargo],
                      'embargo_sessions': days[start-embargo:start],
                      'evaluation_sessions': days[start:min(start+test, limit)]})
    start = len(days)-holdout
    folds.append({'name': 'final_holdout', 'kind': 'FINAL_HOLDOUT',
                  'context_sessions': days[:start-embargo],
                  'embargo_sessions': days[start-embargo:start],
                  'evaluation_sessions': days[start:]})
    return {'version': VERSION, 'rules': RULES.copy(), 'kt_version': KT_VERSION,
            'evaluator_source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'config': {'initial': initial, 'test': test, 'holdout': holdout, 'embargo': embargo},
            'sessions': days, 'horizon_minutes': metadata['horizon_minutes'], 'folds': folds,
            'replay_identity': {key: metadata[key] for key in
                                ('decision_chain_sha256', 'source_rows_sha256', 'engine_source_sha256')},
            'holdout_caveat': 'Retrospective partition, not proof the data was never previously inspected.'}


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as file:
        file.write(json.dumps(value, indent=2, allow_nan=False)+'\n')


def freeze_plan(replay, output, **config):
    with closing(source_connection(replay)) as db:
        plan = build_plan(manifest(db), **config)
        plan['replay_labels_sha256'] = labels_digest(db)
        plan['plan_sha256'] = digest(plan)
        write_new(output, plan)
    return plan


def validate_plan(plan, metadata, label_hash):
    expected = build_plan(metadata, **plan['config'])
    expected['replay_labels_sha256'] = label_hash
    expected['plan_sha256'] = digest(expected)
    require(plan == expected, 'Plan changed, unsupported rules, or replay identity mismatch')


def verified_samples(db, metadata):
    """Stream verified frozen decisions; no mutation, live recorder or model fitting."""
    chain = '0'*64
    decisions = Counter()
    labels = Counter()
    horizon = metadata['horizon_minutes']
    cursor = iter(db.execute('SELECT decision_id,symbol,payload,prediction_sha256 '
                             'FROM replay_labels ORDER BY decision_id,symbol'))
    count = 0
    for rid, known_at, payload, value, previous in db.execute(
            'SELECT id,known_at,payload,sha256,previous_sha256 FROM replay_decisions ORDER BY id'):
        record = json.loads(payload)
        require(previous == chain and digest({'previous': chain, 'record': record}) == value,
                'Broken frozen-decision audit chain')
        chain = value
        at = stamp(known_at)
        day = str(at.date())
        require(day in metadata['sessions'] and count//375 < len(metadata['sessions'])
                and day == metadata['sessions'][count//375], 'Unexpected session/order')
        opening = datetime.combine(at.date(), time(9, 16), IST)
        require(at == opening+timedelta(minutes=count % 375), 'Missing or duplicate decision minute')
        require(record['known_at'] == known_at and stamp(record['bar_start']) == at-timedelta(minutes=1),
                'Decision clock mismatch')
        require(record['version'] == REPLAY_VERSION and record['kt_version'] == KT_VERSION
                and record['evidence_partition'] == 'historical_bootstrap', 'Mixed decision versions/partition')
        decision = record['decision']
        capture = record['capture']
        require(capture['engine_source_sha256'] == metadata['engine_source_sha256'], 'Mixed engine versions')
        require(decision['calibrated_probability'] is None and decision['probability'] is None
                and decision['calibration_eligible'] is False and decision['live_evidence_eligible'] is False
                and decision['authorization'] == 'NONE' and decision['status'] == 'NO_SETUP'
                and decision['operator_action'] == 'WAIT', 'Unsafe historical decision')
        decisions[decision['status']] += 1
        for symbol in sorted(KEYS):
            raw = next(cursor, None)
            require(raw is not None and raw[0] == rid and raw[1] == symbol and raw[3] == value,
                    'Missing, orphaned or mismatched label')
            label = json.loads(raw[2])
            direction = capture['momentum'][symbol]['state']
            require(direction in {'CE', 'PE', 'CONFLICT', 'NEUTRAL', 'UNAVAILABLE', 'DATA_QUALITY_BLOCK'},
                    'Unknown component state')
            require(label['kind'] == 'INDEX_FORWARD_MOVE' and label['horizon_minutes'] == horizon
                    and label['component_direction'] == direction and label['calibration_eligible'] is False
                    and label['trade_outcome_eligible'] is False, 'Invalid label contract')
            status = label['status']
            require(status in {'COMPLETE', 'CENSORED_SESSION_END', 'CENSORED_MISSING_MINUTES',
                               'MISSING_REFERENCE'}, 'Unknown label status')
            labels[status] += 1
            end = at+timedelta(minutes=horizon)
            expected_status = ('COMPLETE' if end <= datetime.combine(at.date(), time(15, 30), IST)
                               else 'CENSORED_SESSION_END')
            require(status == expected_status, 'Label coverage conflicts with complete source session')
            if status == 'COMPLETE':
                require(stamp(label['end_at']) == end and end <= datetime.combine(at.date(), time(15, 30), IST)
                        and label['observations'] == horizon, 'Invalid outcome horizon')
                for key in ('return_bps', 'delta_points', 'reference_close', 'max_up_points', 'max_down_points'):
                    require(type(label[key]) in (int, float) and isfinite(label[key]), 'Nonfinite label')
                require(label['reference_close'] > 0 and
                        abs(label['return_bps']-label['delta_points']/label['reference_close']*10000) < 1e-8,
                        'Inconsistent return')
                window = capture['windows'][symbol]['1']
                require(window and label['reference_close'] == window[-1]['close']
                        and stamp(window[-1]['ts']) == at-timedelta(minutes=1),
                        'Label reference differs from frozen input')
                delta = label['delta_points']
                agreement = (delta > 0 if direction == 'CE' else delta < 0) if direction in {'CE', 'PE'} else None
                require(label['direction_agrees'] is agreement and label['direction_label'] ==
                        ('UP' if delta > 0 else 'DOWN' if delta < 0 else 'FLAT'), 'Inconsistent direction label')
            yield {'id': rid, 'symbol': symbol, 'day': day, 'known_at': at, 'end_at': end,
                   'direction': direction, 'label': label,
                   'grid': (at-opening).total_seconds() % (horizon*60) == 0}
        count += 1
    require(next(cursor, None) is None, 'Orphan or extra labels')
    require(count == len(metadata['sessions'])*375 and chain == metadata['decision_chain_sha256'],
            'Truncated replay or chain mismatch')
    require(dict(decisions) == metadata['decision_counts'] and dict(labels) == metadata['label_counts'],
            'Replay reporting counts mismatch')


def partition_samples(samples, days):
    """Purging uses label availability, including for context-only partitions."""
    chosen = set(days)
    start = datetime.combine(date.fromisoformat(days[0]), time(9, 15), IST)
    end = datetime.combine(date.fromisoformat(days[-1]), time(15, 30), IST)
    retained, purged = [], 0
    for sample in samples:
        if sample['day'] not in chosen:
            continue
        if sample['known_at'] < start or sample['end_at'] > end:
            purged += 1
        else:
            retained.append(sample)
    return retained, purged


def summarize(samples, sessions):
    """Keep each index separate; fixed grid selection never depends on outcomes."""
    result = {}
    for symbol in KEYS:
        rows = [s for s in samples if s['symbol'] == symbol]
        grid = [s for s in rows if s['grid']]
        complete = [s for s in grid if s['label']['status'] == 'COMPLETE']
        groups = {}
        for direction in ('CE', 'PE'):
            selected = [s for s in complete if s['direction'] == direction]
            rates = []
            by_day = []
            for day in sessions:
                daily = [s for s in selected if s['day'] == day]
                agreed = sum(s['label']['direction_agrees'] for s in daily)
                rate = agreed/len(daily) if daily else None
                if rate is not None:
                    rates.append(rate)
                by_day.append({'session': day, 'samples': len(daily), 'agreed': agreed,
                               'disagreed_including_flat': len(daily)-agreed, 'agreement_rate': rate})
            agreed = sum(s['label']['direction_agrees'] for s in selected)
            signed = [s['label']['return_bps']*(1 if direction == 'CE' else -1) for s in selected]
            groups[direction] = {'samples': len(selected), 'agreed': agreed,
                                 'disagreed_including_flat': len(selected)-agreed,
                                 'flat': sum(s['label']['direction_label'] == 'FLAT' for s in selected),
                                 'agreement_rate': agreed/len(selected) if selected else None,
                                 'mean_direction_adjusted_index_move_bps': mean(signed) if signed else None,
                                 'sessions_with_samples': len(rates),
                                 'session_mean_agreement_rate': mean(rates) if rates else None,
                                 'session_min_agreement_rate': min(rates) if rates else None,
                                 'session_max_agreement_rate': max(rates) if rates else None,
                                 'by_session': by_day}
        result[symbol] = {'all_observations': len(rows), 'all_label_statuses': dict(Counter(
            s['label']['status'] for s in rows)), 'all_component_states': dict(Counter(s['direction'] for s in rows)),
            'scheduled_grid_observations': len(grid), 'grid_label_statuses': dict(Counter(
                s['label']['status'] for s in grid)), 'grid_component_states': dict(Counter(s['direction'] for s in grid)),
            'complete_grid_observations': len(complete), 'directional': groups}
    return result


def evaluate(replay, plan_path, output):
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    with closing(source_connection(replay)) as db:
        metadata = manifest(db)
        validate_plan(plan, metadata, labels_digest(db))
        samples = list(verified_samples(db, metadata))
        folds = []
        for fold in plan['folds']:
            selected, purged = partition_samples(samples, fold['evaluation_sessions'])
            context, context_purged = partition_samples(samples, fold['context_sessions'])
            folds.append({**fold, 'context_observations': len(context), 'context_purged': context_purged,
                          'evaluation_purged': purged,
                          'pre_purge_label_statuses': dict(Counter(s['label']['status'] for s in samples
                              if s['day'] in fold['evaluation_sessions'])),
                          'metrics': summarize(selected, fold['evaluation_sessions'])})
        stability = defaultdict(list)
        for fold in folds:
            if fold['kind'] != 'WALK_FORWARD':
                continue
            for symbol in KEYS:
                for direction in ('CE', 'PE'):
                    group = fold['metrics'][symbol]['directional'][direction]
                    stability[f'{symbol}_{direction}'].append({'fold': fold['name'], 'samples': group['samples'],
                                                               'agreement_rate': group['agreement_rate']})
        coverage = summarize(samples, plan['sessions'])
        for group in coverage.values():
            del group['directional']  # Never pool held-out performance into development results.
        report = {'version': VERSION, **RULES, 'status': 'DIAGNOSTICS_COMPLETE',
                  'plan_sha256': plan['plan_sha256'], 'replay_identity': plan['replay_identity'],
                  'evaluator_source_sha256': plan['evaluator_source_sha256'],
                  'replay_labels_sha256': plan['replay_labels_sha256'],
                  'holdout_caveat': plan['holdout_caveat'], 'folds': folds,
                  'walk_forward_stability': dict(stability),
                  'all_session_coverage': coverage,
                  'limitations': ['Fixed rules; context sets are never fitted or optimized.',
                                  'Final holdout is reported separately; no pass/fail promotion threshold.',
                                  'Nonoverlapping horizons are still serially dependent and indices correlated.',
                                  'Direction agreement is not probability calibration or a trade win rate.',
                                  'Index moves exclude option performance, fees, slippage and fills.',
                                  'No claim of profitability, independent forward validation or full strategy validation.'],
                  'remaining_gates': ['independent_forward_evidence', 'full_option_evidence_and_outcomes',
                                      'cost_adjusted_usefulness', 'out_of_sample_probability_calibration']}
        write_new(output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('plan', help='Freeze date-only protocol before evaluating performance')
    plan.add_argument('--replay', required=True, type=Path)
    plan.add_argument('--output', required=True, type=Path)
    for name, default in (('initial', 30), ('test', 10), ('holdout', 20), ('embargo', 1)):
        plan.add_argument('--'+name, type=int, default=default)
    score = sub.add_parser('evaluate')
    score.add_argument('--replay', required=True, type=Path)
    score.add_argument('--plan', required=True, type=Path)
    score.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == 'plan':
        result = freeze_plan(args.replay, args.output, initial=args.initial, test=args.test,
                             holdout=args.holdout, embargo=args.embargo)
    else:
        result = evaluate(args.replay, args.plan, args.output)
    print(json.dumps({'output': str(args.output), 'plan_sha256': result['plan_sha256'],
                      'folds': len(result['folds']), 'calibrated_probability': None,
                      'calibration_eligible': False}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
