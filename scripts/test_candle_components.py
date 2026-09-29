from datetime import datetime, timedelta
import unittest

from replay_candle_components import component_records


class CausalReplayTests(unittest.TestCase):
    def fixture(self):
        start=datetime.fromisoformat('2026-05-19T09:15:00+05:30')
        rows={(start+timedelta(minutes=i)).isoformat():
              {'open':100+i,'high':102+i,'low':99+i,'close':101+i,'volume':0}
              for i in range(30)}
        return {s:{k:dict(v) for k,v in rows.items()} for s in ('NIFTY','BANKNIFTY')}

    def test_future_changes_cannot_change_earlier_outputs(self):
        indices=self.fixture()
        before=list(component_records(indices))
        final=max(indices['NIFTY'])
        indices['NIFTY'][final]['close']=1
        after=list(component_records(indices))
        self.assertEqual(before[:-1],after[:-1])
        self.assertTrue(all(r['authorization']=='NONE' and r['probability'] is None for r in after))

    def test_gap_restarts_warmup_instead_of_forward_filling(self):
        indices=self.fixture()
        missing=sorted(indices['NIFTY'])[23]
        del indices['NIFTY'][missing]
        rows=list(component_records(indices))
        self.assertEqual(rows[23]['momentum']['NIFTY']['state'],'UNAVAILABLE')
        self.assertEqual(rows[24]['momentum']['NIFTY']['state'],'UNAVAILABLE')
        self.assertNotEqual(rows[24]['momentum']['BANKNIFTY']['state'],'UNAVAILABLE')


if __name__=='__main__':
    unittest.main()
