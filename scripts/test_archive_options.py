import tempfile
import unittest
import contextlib
import csv
import gzip
import io
import json
from pathlib import Path

from archive_options import Archive, select_contracts, validate_candles
from audit_replay import audit


class ArchiveTests(unittest.TestCase):
    def test_conflicts_are_quarantined_and_nonregular_rows_are_excluded(self):
        first = ['2026-05-19T09:15:00+05:30',100,110,90,105,5,10]
        changed = [first[0],100,110,90,106,5,10]
        outside = ['2026-05-19T15:30:00+05:30',100,110,90,105,5,10]
        invalid = ['2026-05-19T09:16:00+05:30',100,99,90,105,5,10]
        rows, quality = validate_candles([first,changed,outside,invalid], '2026-05-19','2026-05-19')
        self.assertEqual(rows, [])
        self.assertEqual(quality['conflicting_timestamps'],1)
        self.assertEqual(quality['outside_regular_hours'],1)
        self.assertEqual(quality['invalid_rows'],1)

    def test_selection_has_six_legs_and_deterministic_tie_break(self):
        contracts = [{'strike_price':s,'instrument_type':side} for s in [90,100,110,120,130]
                     for side in ['CE','PE']]
        chosen = select_contracts(contracts,115)
        self.assertEqual({c['strike_price'] for c in chosen},{100,110,120})
        self.assertEqual(len(chosen),6)

    def test_existing_observation_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp),'not-a-real-token')
            row = ['2026-05-19T09:15:00+05:30',100,110,90,105,5,10]
            archive.get = lambda path: ({'data':{'candles':[row]}},'request-one')
            contract = {'instrument_key':'NSE_FO|1|26-05-2026'}
            archive.candles(contract,'2026-05-19','2026-05-19')
            row[4] = 106
            _, quality = archive.candles(contract,'2026-05-19','2026-05-19')
            self.assertEqual(quality['stored_conflicts'],1)
            self.assertIn('105.0',archive.db.execute('SELECT payload FROM candles').fetchone()[0])
            archive.db.close()

    def test_missing_minutes_are_not_filled(self):
        rows, _ = validate_candles([
            ['2026-05-19T09:17:00+05:30',100,110,90,105,5,10]],'2026-05-19','2026-05-19')
        self.assertEqual(len(rows),1)

    def test_replay_does_not_use_a_later_quote_for_an_earlier_minute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            day = '2026-05-19'
            first = day+'T09:15:00+05:30'
            later = day+'T09:16:00+05:30'
            for symbol in ('NIFTY','BANKNIFTY'):
                with (root/f'{symbol}-1minute.csv').open('w',newline='') as f:
                    writer=csv.writer(f)
                    writer.writerow(['timestamp_IST','close'])
                    writer.writerows([[first,100],[later,101]])
            store = Archive(root,'not-a-real-token')
            selections=[]
            for i in range(12):
                key=f'NSE_FO|{i}'
                selections.append({'status':'SELECTED','day':day,'instrument_key':key})
                store.db.execute('INSERT INTO candles VALUES(?,?,?,?)',
                                 (key,later,json.dumps([later,100,110,90,105,5,10]),'test'))
            store.db.commit()
            store.db.close()
            manifest=root/'manifest-test.json'
            manifest.write_text(json.dumps({'index_archive':str(root),'sessions':[day],
                                             'selections':selections}))
            with contextlib.redirect_stdout(io.StringIO()):
                audit(root,manifest)
            with gzip.open(root/'replay-input-audit-test.jsonl.gz','rt') as f:
                rows=[json.loads(line) for line in f]
            self.assertEqual(rows[0]['available_selected_option_candles'],0)
            self.assertEqual(rows[1]['available_selected_option_candles'],12)
            self.assertEqual(rows[0]['known_at'],later)
            self.assertTrue(all(r['decision_gate_result']['authorization']=='NONE' for r in rows))
            self.assertTrue(all(r['probability'] is None for r in rows))


if __name__ == '__main__':
    unittest.main()
