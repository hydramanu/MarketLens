"""Local single-user research server. No brokerage integration or trading."""
import argparse
import io
import json
import os
import re
import ssl
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
from engine import ROOT, analyze, clean, query, store

DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
LOCK = threading.RLock()
CACHE = {}
LAST_REFRESH = {}
APPLE_URL = 'https://raw.githubusercontent.com/plotly/datasets/master/finance-charts-apple.csv'


def fetch(url):
    # Explicit verified context avoids inheriting host TLS key-log settings.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    request = urllib.request.Request(url, headers={'User-Agent': 'MarketLens-Learning-Project/1.0'})
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        return response.read(5_000_001)


def register(name, frame, meta):
    frame, quality = clean(frame)
    meta = {**meta, 'id': name, 'loaded_at': datetime.now(timezone.utc).isoformat()}
    with LOCK:
        store(frame, name, DATA/'market.db')
        CACHE[name] = (frame, quality, meta)


def apple():
    path = DATA/'apple.csv'
    if not path.exists():
        path.write_bytes(fetch(APPLE_URL))
    raw = pd.read_csv(path)
    raw = raw.rename(columns={'Date':'date', **{f'AAPL.{c.title()}':c for c in ['open','high','low','close','volume']}})
    register('AAPL', raw, {'name':'Apple · historical study', 'source':'Plotly public example dataset',
        'source_url': APPLE_URL, 'asset_class':'equity', 'mode':'Historical sample · 2015–2017',
        'price_basis':'Raw OHLC close; adjusted-close column is not used. Not total return.'})


def refresh_crypto(symbol):
    if symbol not in ('BTC-USD', 'ETH-USD'):
        raise ValueError('Unsupported live product.')
    with LOCK:
        if time.monotonic() - LAST_REFRESH.get(symbol, -1000) < 60:
            raise ValueError('Please wait 60 seconds between provider refreshes.')
        LAST_REFRESH[symbol] = time.monotonic()
    url = f'https://api.exchange.coinbase.com/products/{symbol}/candles?granularity=86400'
    raw = json.loads(fetch(url))
    if not isinstance(raw, list):
        raise ValueError('Provider did not return candles.')
    d = pd.DataFrame(raw, columns=['time','low','high','open','close','volume'])
    d['date'] = pd.to_datetime(d.time, unit='s', utc=True).dt.strftime('%Y-%m-%d')
    # Exclude today's incomplete daily candle; ticker is separately labelled.
    d = d[d.date < datetime.now(timezone.utc).strftime('%Y-%m-%d')]
    register(symbol, d, {'name':symbol, 'source':'Coinbase Exchange public API', 'source_url':url,
        'asset_class':'crypto', 'mode':'Refreshed daily candles · completed UTC days only',
        'price_basis':'Single-exchange USD close; volume is base asset units.'})


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT/'web'), **kwargs)

    def json_response(self, data, status=200):
        body = json.dumps(data, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        p = parse_qs(parsed.query)
        try:
            if parsed.path == '/api/catalog':
                with LOCK:
                    return self.json_response([{'id':k, **v[2], 'first':v[0].date.iloc[0], 'last':v[0].date.iloc[-1]} for k,v in CACHE.items()])
            if parsed.path == '/api/analysis':
                name = p.get('dataset',['AAPL'])[0]
                cutoff = p.get('cutoff',[None])[0]
                window = int(p.get('window',['252'])[0])
                if window not in (63,126,252,1000):
                    raise ValueError('Unsupported window.')
                with LOCK:
                    if name not in CACHE:
                        raise ValueError('Dataset is not loaded.')
                    result = analyze(*CACHE[name], cutoff, window)
                    result['sql'] = query(DATA/'market.db', name, result['receipt']['end'])
                return self.json_response(result)
            if parsed.path == '/api/ticker':
                symbol = p.get('symbol',['BTC-USD'])[0]
                if symbol not in ('BTC-USD','ETH-USD'):
                    raise ValueError('Unsupported ticker.')
                raw = json.loads(fetch(f'https://api.exchange.coinbase.com/products/{symbol}/ticker'))
                return self.json_response({'symbol':symbol, 'price':float(raw['price']), 'time':raw['time'],
                    'source':'Coinbase Exchange', 'mode':'Polled quote, not a streaming feed'})
            if parsed.path.startswith('/api/'):
                return self.json_response({'error':'Not found'},404)
            return super().do_GET()
        except (ValueError, KeyError) as e:
            self.json_response({'error':str(e)},400)
        except Exception:
            self.json_response({'error':'Provider unavailable or malformed response. Existing dataset is unchanged; try again later.'},502)

    def do_POST(self):
        # Local write endpoints: same-origin only, JSON only, bounded payloads.
        origin = self.headers.get('Origin')
        host = self.headers.get('Host')
        if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}') or (origin and origin not in (f'http://{host}',)):
            return self.json_response({'error':'Origin not allowed'},403)
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            return self.json_response({'error':'JSON required'},415)
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 2_000_000:
                raise ValueError('Payload must be between 1 byte and 2 MB.')
            body = json.loads(self.rfile.read(length))
            if self.path == '/api/refresh':
                refresh_crypto(body.get('symbol','BTC-USD'))
            elif self.path == '/api/import':
                if body.get('asset_class') not in ('equity','crypto'):
                    raise ValueError('Choose equity or crypto.')
                register('IMPORT', pd.read_csv(io.StringIO(body['csv'])), {'name':'Your imported dataset',
                    'source':'User CSV · local only', 'source_url':None, 'asset_class':body['asset_class'],
                    'mode':'Imported daily data', 'price_basis':'User-supplied OHLC; adjustment basis unverified.'})
            else:
                return self.json_response({'error':'Not found'},404)
            return self.json_response({'ok':True})
        except (ValueError, KeyError, pd.errors.ParserError) as e:
            self.json_response({'error':str(e)},400)
        except Exception:
            self.json_response({'error':'Refresh failed. Existing dataset remains available. Check your connection and provider availability.'},502)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8790)
    args = parser.parse_args()
    try:
        apple()
    except Exception as e:
        print('Historical seed could not load. Import a CSV in the app to begin.', flush=True)
    print(f'MarketLens: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port), Handler).serve_forever()
