from copy import deepcopy
from types import SimpleNamespace

import pytest

from dantex.replay_capture import replay_capture
from dantex.validation_recorder import ValidationRecorder


def test_capture_keeps_quotes_and_greeks_after_source_mutates(tmp_path, monkeypatch):
    recorder = ValidationRecorder(str(tmp_path/'records.sqlite3'))
    sent = []
    monkeypatch.setattr(recorder, '_external_write', lambda row: sent.append(deepcopy(row)) or True)
    options = {'NIFTY': {'strikes': [{'call': {'instrument_key': 'exact-contract',
                      'bid_price': 99, 'ask_price': 101, 'delta': .5, 'theta': -2}}]}}
    snap = {'replay': replay_capture(options=options)}
    options['NIFTY']['strikes'][0]['call']['bid_price'] = 1
    recorder.record_duel({'state':'NO_EDGE','readiness':{}}, {'authorization':'NONE'}, snap)
    local = recorder.recent(1)[0]['market_snapshot']
    assert local == sent[0]['market_snapshot']
    assert local['replay']['options']['NIFTY']['strikes'][0]['call']['bid_price'] == 99
    assert len(local['replay']['engine_source_sha256']) == 64
    assert not local['replay']['calibration_eligible']


@pytest.mark.parametrize('sector_failure', [False, True])
def test_decision_capture_saves_exact_option_structure_and_quote_inputs(monkeypatch, sector_failure):
    from dantex import api

    snapshots = {s: {'status':'OK','spot':23000,'expiry':'2026-09-29',
        'strikes':[{'strike':23000,'call':{'instrument_key':'call-key','ltp':100,
             'bid_price':99,'ask_price':101,'delta':.5,'theta':-1,'volume':100000,'oi':30000}}],
        'path_response':{'state':'NO_EDGE','session_date':'2026-09-25',
                         'last_sample_at':'2026-09-25T12:00:00+05:30'}} for s in ('NIFTY','BANKNIFTY')}
    structure = {'status':'OK','recent_candles':[{'close':1}],
                 'prior_day':{'high':2,'low':.5,'close':1},'evidence_eligible':False}
    monkeypatch.setattr(api.instrument_master,'refresh_async',lambda:None)
    monkeypatch.setattr(api.options_intelligence,'snapshot',lambda s:pytest.fail('must reuse observer snapshots'))
    monkeypatch.setattr(api,'structure_snapshot',lambda s:deepcopy(structure))
    monkeypatch.setattr(api,'paper_lifecycle',lambda *args:{'authorization':'NONE'})
    monkeypatch.setattr(api.UpstoxCredentials,'from_env',lambda:SimpleNamespace(analytics_token='test'))
    monkeypatch.setattr(api,'freshness_gate',lambda **kwargs:{'eligible':False,'reasons':['not live']})
    records = []
    monkeypatch.setattr(api.validation_recorder,'record_duel',lambda *args:records.append(deepcopy(args)))

    def quotes(self, keys):
        if sector_failure and keys == list(api.SECTOR_INDEX_KEYS.values()):
            raise RuntimeError('simulated failure')
        return {'data':{key:{'last_price':98,'net_change':-2,
            'timestamp':'2026-09-25T12:00:00+05:30'} for key in keys}}
    monkeypatch.setattr(api.UpstoxRestClient,'full_market_quotes',quotes)
    result = api.evaluate_option_duel(snapshots['NIFTY'],snapshots['BANKNIFTY'])
    capture = records[0][2]['replay']
    assert capture['options'] == snapshots
    assert capture['structures']['NIFTY'] == structure
    assert capture['evidence_families'] == result['evidence_families']
    assert capture['quote_inputs']['breadth']['requested_keys'] == api.NIFTY_BREADTH_KEYS
    assert capture['quote_inputs']['breadth']['response']['data']
    assert result['decision']['authorization'] == 'NONE'
    if sector_failure:
        assert capture['quote_inputs']['error_type'] == 'RuntimeError'
    else:
        assert capture['quote_inputs']['volatility']['response']['data']


def test_unavailable_option_snapshot_is_recorded(monkeypatch):
    from dantex import api
    records=[]
    monkeypatch.setattr(api.instrument_master,'refresh_async',lambda:None)
    monkeypatch.setattr(api.validation_recorder,'record_duel',lambda *args:records.append(args))
    result=api.evaluate_option_duel({'status':'MASTER_LOADING'},{'status':'OK'})
    assert result['state']=='DATA_NOT_READY'
    assert records[0][2]['replay']['kind']=='data_not_ready'
    assert records[0][1]['authorization']=='NONE'
