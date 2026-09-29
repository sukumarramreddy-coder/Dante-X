"""Persistent paper lifecycle using the existing premium reference geometry.

GO is a simulated trigger observation, never broker execution. No position sizing,
fill assumptions or calibrated probabilities are introduced here.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from math import isfinite
from uuid import uuid4

from .domain import Lifecycle, Side
from .freshness import IST, gate
from .management import manage_open_trade
from .session import INTRADAY_POLICY, intraday_session_status
from .state import ArmedPlan, LiveSignalState, evaluate_armed

ACTIVE = {'WAIT', 'GO', 'HOLD', 'RUN', 'WARNING'}


def valid_price(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(value) and value > 0


class ShadowLifecycle:
    def __init__(self, path):
        self.path = path
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS shadow_lifecycle (slot INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS shadow_lifecycle_events (id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL, payload TEXT NOT NULL)')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def snapshot(self):
        with self._connect() as db:
            row = db.execute('SELECT payload FROM shadow_lifecycle WHERE slot=1').fetchone()
            events = db.execute('SELECT payload FROM shadow_lifecycle_events ORDER BY id DESC LIMIT 30').fetchall()
        return {'current': json.loads(row[0]) if row else None,
                'events': [json.loads(e[0]) for e in events], 'mode': 'shadow',
                'probability': None, 'calibration_status': 'UNCALIBRATED'}

    def advance(self, decision, families, options, now=None):
        now = (now or datetime.now(IST)).astimezone(IST)
        timestamp = (options.get('path_response') or {}).get('last_sample_at')
        fresh = bool((families.get('readiness') or {}).get('live_evidence_ready'))
        fresh = fresh and gate(source='PAPER_OPTIONS', timestamp=timestamp, now=now)['eligible']
        session = intraday_session_status(now)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM shadow_lifecycle WHERE slot=1').fetchone()
            current = json.loads(row[0]) if row else None
            prior_status = current.get('status') if current else None
            prior_id = current.get('signal_id') if current else None
            if current and current['status'] in ACTIVE:
                if current['session_date'] != now.date().isoformat() or session in {'force_exit', 'closed', 'preopen'}:
                    current['status'] = 'CANCEL' if current['status'] == 'WAIT' else 'EXIT'
                    current['reason'] = 'Intraday session ended; no execution or exit price is assumed.'
                    current['exit_price'] = None
                elif current['status'] == 'WAIT' and session != 'entry_allowed':
                    current['status'] = 'CANCEL'
                    current['reason'] = 'Entry cutoff reached before the trigger.'
                elif not fresh:
                    return self._paused(current, 'Required live evidence is stale or unavailable.')
                elif datetime.fromisoformat(timestamp) <= datetime.fromisoformat(current['last_observation_at']):
                    return self._paused(current, 'Waiting for a newer option observation.')
                else:
                    leg = next((r.get(side) for r in options.get('strikes', []) for side in ('call', 'put')
                                if (r.get(side) or {}).get('instrument_key') == current['contract']['instrument_key']), None)
                    if options.get('expiry') != current['contract']['expiry'] or not leg or not valid_price(leg.get('ltp')):
                        return self._paused(current, 'The locked contract has no current quote; it has not been replaced by a new ATM contract.')
                    price = leg['ltp']
                    direction_ok = families.get('state') == current['direction'] + '_EVIDENCE'
                    current['last_observation_at'] = timestamp
                    current['current_premium'] = price
                    if current['status'] == 'WAIT':
                        if not direction_ok:
                            current.update(status='CANCEL', reason='Fresh evidence no longer supports the waiting setup.')
                        else:
                            plan = ArmedPlan(current['signal_id'], Side.BULLISH, current['reference_entry'],
                                             current['reference_stop'], datetime.fromisoformat(current['created_at']),
                                             datetime.fromisoformat(current['expires_at']))
                            result = evaluate_armed(LiveSignalState(plan, Lifecycle.ARMED, now, 'paper waiting'), price=price, at=now)
                            current['status'] = 'WAIT' if result.lifecycle == Lifecycle.ARMED else result.lifecycle.value
                            current['reason'] = result.reason
                            if current['status'] == 'GO':
                                current['trigger_observed_at'] = now.isoformat()
                                current['trigger_observed_premium'] = price
                                current['reason'] = 'Locked premium trigger observed on a later fresh sample; simulated GO, no order placed.'
                    else:
                        path = (options.get('path_response') or {}).get('state')
                        confirming = direction_ok and path == current['direction'] + '_STRENGTHENING'
                        result = manage_open_trade(side=Side.BULLISH, current=price, stop=current['reference_stop'],
                                                   target1=current['reference_t1'], target2=current['reference_t2'],
                                                   path_score=100 if confirming else 0, option_confirming=confirming)
                        current.update(status=result.lifecycle.value, reason=result.reason)
                        if current['status'] == 'EXIT':
                            current['exit_price'] = price
            elif fresh and session == 'entry_allowed' and decision.get('status') == 'DETECTED':
                contract = decision.get('contract') or {}
                levels = [decision.get(k) for k in ('reference_stop', 'reference_entry', 'reference_t1', 'reference_t2')]
                if not contract.get('instrument_key') or not contract.get('expiry') or not all(valid_price(v) for v in levels) or not levels[0] < levels[1] < levels[2] < levels[3]:
                    return self._paused(current, 'A complete valid paper plan is required.')
                # Do not re-arm from the exact observation that closed a prior plan.
                if current and timestamp <= current.get('last_observation_at', ''):
                    return self._paused(current, 'Waiting for a new setup observation.')
                current = {**decision, 'status': 'WAIT', 'signal_id': uuid4().hex,
                           'session_date': now.date().isoformat(), 'created_at': now.isoformat(),
                           'expires_at': datetime.combine(now.date(), INTRADAY_POLICY.entry_cutoff, IST).isoformat(),
                           'last_observation_at': timestamp,
                           'reason': 'Paper plan locked. Waiting for a later fresh premium observation to reach the reference entry.'}
            else:
                return self._paused(current, decision.get('reason') or 'Waiting for fresh evidence and an eligible setup.')
            current.update(authorization='SHADOW_ONLY' if current['status'] in ACTIVE else 'NONE',
                           probability=None, tracking_status='CURRENT', updated_at=now.isoformat(),
                           simulation=True, note='Paper premium lifecycle only. No broker fills, structural execution approval or calibrated probability.')
            db.execute('INSERT OR REPLACE INTO shadow_lifecycle VALUES (1,?)', (json.dumps(current),))
            if current['status'] != prior_status or current['signal_id'] != prior_id:
                db.execute('INSERT INTO shadow_lifecycle_events(recorded_at,payload) VALUES (?,?)', (now.isoformat(), json.dumps(current)))
            return current

    @staticmethod
    def _paused(current, reason):
        return {**(current or {}), 'status': 'WAIT', 'previous_status': (current or {}).get('status'),
                'tracking_status': 'PAUSED', 'authorization': 'NONE', 'probability': None,
                'reason': reason, 'simulation': True}
