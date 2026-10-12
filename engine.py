"""Auditable cleaning and causal, close-to-close market statistics."""
import hashlib
import io
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
FIELDS = ['open', 'high', 'low', 'close', 'volume']


def clean(frame):
    frame = frame.copy()
    required = ['date'] + FIELDS
    if not set(required).issubset(frame.columns):
        raise ValueError('CSV needs date, open, high, low, close, volume columns.')
    frame = frame[required]
    original = len(frame)
    frame['date'] = pd.to_datetime(frame['date'], errors='coerce', utc=True).dt.strftime('%Y-%m-%d')
    for col in FIELDS:
        frame[col] = pd.to_numeric(frame[col], errors='coerce')
    invalid = frame.isna().any(axis=1) | ~np.isfinite(frame[FIELDS]).all(axis=1)
    invalid |= (frame[['open', 'high', 'low', 'close']] <= 0).any(axis=1) | (frame.volume < 0)
    invalid |= (frame.high < frame[['open', 'close', 'low']].max(axis=1))
    invalid |= (frame.low > frame[['open', 'close', 'high']].min(axis=1))
    invalid |= frame.date > datetime.now(timezone.utc).strftime('%Y-%m-%d')
    removed = int(invalid.sum())
    frame = frame[~invalid]
    duplicates = int(frame.duplicated('date', keep='last').sum())
    frame = frame.drop_duplicates('date', keep='last').sort_values('date').reset_index(drop=True)
    if len(frame) < 22:
        raise ValueError('At least 22 valid daily observations are required.')
    return frame, {'input_rows': original, 'invalid_rows': removed, 'duplicate_rows': duplicates,
                   'accepted_rows': len(frame), 'retained_pct': round(len(frame) / original * 100, 2)}


def calculate(frame, periods=252):
    d = frame.copy()
    d['return'] = d.close.pct_change(fill_method=None)
    d['volatility'] = d['return'].rolling(20, min_periods=20).std(ddof=1) * np.sqrt(periods) * 100
    d['drawdown'] = (d.close / d.close.cummax() - 1) * 100
    d['volume_change'] = d.volume.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan) * 100
    # Baseline excludes the observation being scored.
    baseline = d.volume.shift(1).rolling(20, min_periods=20).mean()
    d['volume_ratio'] = d.volume / baseline.replace(0, np.nan)
    d['ma20'] = d.close.rolling(20, min_periods=20).mean()
    return d


def safe(value):
    return None if pd.isna(value) or not np.isfinite(value) else round(float(value), 4)


def analyze(frame, quality, meta, cutoff=None, window=252):
    if cutoff:
        frame = frame[frame.date <= cutoff]
    frame = frame.tail(window).reset_index(drop=True)
    if len(frame) < 22:
        raise ValueError('This replay range needs at least 22 observations.')
    periods = 365 if meta.get('asset_class') == 'crypto' else 252
    d = calculate(frame, periods)
    returns = d['return'].dropna()
    q05 = returns.quantile(.05)
    tail = returns[returns <= q05]
    last = d.iloc[-1]
    days_old = (datetime.now(timezone.utc).date() - pd.Timestamp(last.date).date()).days
    gaps = int((pd.to_datetime(d.date).diff().dt.days > (1 if periods == 365 else 4)).sum())
    digest = hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
    metrics = {'close': safe(last.close), 'daily_return': safe(last['return'] * 100),
        'period_return': safe((last.close / d.close.iloc[0] - 1) * 100),
        'volatility': safe(last.volatility), 'max_drawdown': safe(d.drawdown.min()),
        'var95': safe(max(0, -q05 * 100)), 'expected_shortfall': safe(max(0, -tail.mean() * 100)),
        'volume_ratio': safe(last.volume_ratio), 'volume_change': safe(last.volume_change)}
    observations = [
        f"Close changed {metrics['period_return']:+.2f}% from {d.date.iloc[0]} to {last.date}; this is a price return, not dividend-inclusive total return.",
        f"The latest 20-observation annualized volatility is {metrics['volatility']:.2f}% using {periods} periods per year and sample standard deviation.",
        f"The largest peak-to-trough drawdown within this window was {metrics['max_drawdown']:.2f}%; peaks before the window are excluded.",
        f"The historical 5th-percentile daily-return loss is {metrics['var95']:.2f}%; the mean loss in that tail is {metrics['expected_shortfall']:.2f}%. These are descriptive, not forecasts.",
        f"{gaps} unusually long date gaps appear in this window. No prices were filled or interpolated; adjacent observations across gaps may span multiple days."
    ]
    points = [{k: (str(row[k]) if k == 'date' else safe(row[k])) for k in
               ['date','close','volume','return','volatility','drawdown','volume_ratio','ma20']} for _, row in d.iterrows()]
    alerts = []
    if metrics['volume_ratio'] is not None and metrics['volume_ratio'] >= 2:
        alerts.append('Latest volume is at least twice the previous 20-observation average.')
    if abs(metrics['daily_return']) >= 3:
        alerts.append('Latest close-to-close move exceeds 3%. Check corporate actions and source data.')
    if days_old > (2 if periods == 365 else 5):
        alerts.append('Historical/stale snapshot: do not interpret this as today’s market.')
    return {'meta': meta, 'quality': {**quality, 'gap_count': gaps, 'age_days': days_old},
        'metrics': metrics, 'points': points, 'observations': observations, 'alerts': alerts,
        'receipt': {'sha256': digest, 'start': d.date.iloc[0], 'end': str(last.date), 'rows': len(d),
                    'annualization': periods, 'volatility_window': 20, 'method_version': '1.0.0'}}


def store(frame, dataset, database):
    with closing(sqlite3.connect(database)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS prices (dataset TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(dataset,date))')
        db.execute('DELETE FROM prices WHERE dataset=?', (dataset,))
        db.executemany('INSERT INTO prices VALUES (?,?,?,?,?,?,?)',
                       [(dataset, *row) for row in frame.itertuples(index=False, name=None)])


def query(database, dataset, cutoff):
    with closing(sqlite3.connect(database)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute((ROOT/'sql/analysis.sql').read_text(), (dataset, cutoff))]
