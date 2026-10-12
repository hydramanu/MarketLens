import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from engine import analyze, calculate, clean, query, store


def fixture(n=80):
    close = np.arange(n,dtype=float)+100
    return pd.DataFrame({'date':pd.date_range('2024-01-01',periods=n).strftime('%Y-%m-%d'),
        'open':close,'high':close+2,'low':close-2,'close':close,'volume':np.full(n,1000.)})


class AnalyticsTests(unittest.TestCase):
    def test_invalid_and_duplicate_rows_are_reported(self):
        d=fixture(); d.loc[0,'close']=-1
        d=pd.concat([d,d.iloc[[-1]]],ignore_index=True)
        result,q=clean(d)
        self.assertEqual(q['invalid_rows'],1)
        self.assertEqual(q['duplicate_rows'],1)
        self.assertEqual(len(result),79)

    def test_return_and_drawdown(self):
        d=fixture(22);d['close']=100.;d.loc[21,'close']=80.
        c=calculate(d)
        self.assertAlmostEqual(c['return'].iloc[-1],-.2)
        self.assertAlmostEqual(c.drawdown.iloc[-1],-20)

    def test_replay_does_not_use_future_observations(self):
        d,q=clean(fixture());meta={'asset_class':'equity'}
        a=analyze(d,q,meta,cutoff='2024-02-10')
        changed=d.copy();changed.loc[changed.date>'2024-02-10','close']=100000
        b=analyze(changed,q,meta,cutoff='2024-02-10')
        self.assertEqual(a['metrics'],b['metrics'])
        self.assertEqual(a['receipt'],b['receipt'])

    def test_volume_baseline_excludes_current_day(self):
        d=fixture();d.loc[79,'volume']=10000
        self.assertEqual(calculate(d).volume_ratio.iloc[-1],10)

    def test_zero_volume_produces_missing_ratio(self):
        d=fixture();d['volume']=0
        self.assertTrue(pd.isna(calculate(d).volume_ratio.iloc[-1]))

    def test_sql_and_pandas_returns_agree(self):
        d,q=clean(fixture())
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'db.sqlite';store(d,'TEST',path)
            rows=query(path,'TEST',d.date.iloc[-1])
            self.assertAlmostEqual(rows[0]['return_pct'],calculate(d)['return'].iloc[-1]*100,places=4)

    def test_short_or_malformed_inputs_rejected(self):
        with self.assertRaises(ValueError):clean(fixture(10))
        with self.assertRaises(ValueError):clean(pd.DataFrame({'x':[1]}))

    def test_crypto_annualization(self):
        d,q=clean(fixture())
        a=analyze(d,q,{'asset_class':'equity'})
        b=analyze(d,q,{'asset_class':'crypto'})
        self.assertAlmostEqual(b['metrics']['volatility']/a['metrics']['volatility'],np.sqrt(365/252),places=3)


if __name__=='__main__':unittest.main()
