"""Build the public historical teaching snapshot from the saved source research.

Run: python scripts/build_market_history.py --research-dir PATH
The research directory contains raw/FRED_ID.csv, raw/FRED_ID.metadata.json,
raw/french_daily.csv, source_manifest.json and outputs/vintage_checks.csv.
Only the explicit public-source allowlist is copied. The missing long CPI series
is fetched from FRED with a server-side key. Raw source hashes are retained.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from datetime import datetime,timezone
import pandas as pd
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_history_catalog import SERIES


def write_csv(frame,path):
    payload=frame.to_csv(index=False,date_format='%Y-%m-%d',float_format='%.8f').encode()
    path.write_bytes(gzip.compress(payload,mtime=0))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'data/market_history')
    args=parser.parse_args()
    root=args.research_dir
    dest=args.output
    dest.mkdir(parents=True,exist_ok=True)
    research=json.loads((root/'source_manifest.json').read_text())
    macro=[]
    metadata={}
    for series,definition in SERIES.items():
        raw=root/'raw'/f'{series}.csv'
        meta=root/'raw'/f'{series}.metadata.json'
        if raw.exists():
            original=raw.read_bytes()
            digest=hashlib.sha256(original).hexdigest()
            if research['files'].get(raw.name) != digest:
                raise ValueError(f'Research hash mismatch: {series}')
            frame=pd.read_csv(io.BytesIO(original))
            details=json.loads(meta.read_text())
            retrieved=research['retrieved_at']
        else:
            key=os.environ.get('FRED_API_KEY','')
            if not key:
                raise ValueError('FRED_API_KEY required for missing long-run CPI source.')
            params={'api_key':key,'file_type':'json','series_id':series}
            try:
                obs=requests.get('https://api.stlouisfed.org/fred/series/observations',params={**params,'observation_start':'1913-01-01','observation_end':'2024-12-31'},timeout=40)
                obs.raise_for_status()
                frame=pd.DataFrame(obs.json()['observations'])[['date','value']]
                response=requests.get('https://api.stlouisfed.org/fred/series',params=params,timeout=30)
                response.raise_for_status()
                details=response.json()['seriess'][0]
            except Exception:
                raise ValueError(f'FRED source unavailable: {series}') from None
            digest=hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
            retrieved=datetime.now(timezone.utc).isoformat(timespec='seconds')
        frame['date']=pd.to_datetime(frame.date,errors='coerce')
        frame['value']=pd.to_numeric(frame.value,errors='coerce')
        frame=frame.dropna().loc[lambda d:(d.date>='1913-01-01') & (d.date<='2024-12-31')]
        if frame.date.duplicated().any():
            raise ValueError('Duplicate source dates: '+series)
        frame['series_id']=series
        macro.append(frame[['date','series_id','value']])
        metadata[series]={
            'name':definition.name,'source_title':details['title'],
            'url':f'https://fred.stlouisfed.org/series/{series}',
            'raw_units':details['units'],'frequency':details['frequency'],
            'seasonal_adjustment':details['seasonal_adjustment'],
            'raw_sha256':digest,'retrieved_at':retrieved,
            'snapshot_start':frame.date.min().date().isoformat(),
            'snapshot_end':frame.date.max().date().isoformat(),
            'method':'FRED observations; date and value; no filling or vintage substitution.',
            'request':{'provider':'FRED API','method':'series/observations','series_id':series,
                       'observation_start':'1776-07-04' if raw.exists() else '1913-01-01',
                       'observation_end':research['observation_cutoff'] if raw.exists() else '2024-12-31',
                       'snapshot_observation_end':'2024-12-31','limit':100000,'sort_order':'asc','file_type':'json'},
        }
    write_csv(pd.concat(macro).sort_values(['series_id','date']),dest/'macro.csv.gz')
    raw=root/'raw/french_daily.csv'
    digest=hashlib.sha256(raw.read_bytes()).hexdigest()
    if research['files'].get(raw.name) != digest:
        raise ValueError('Research hash mismatch: French daily factors')
    factors=pd.read_csv(raw,parse_dates=['date'])
    factors=factors.loc[factors.date<='2024-12-31']
    if (factors[['Mkt-RF','RF']] <= -99).any().any():
        raise ValueError('Missing-return sentinel in benchmark')
    market=pd.DataFrame({'date':factors.date,'return_pct':factors['Mkt-RF']+factors.RF})
    write_csv(market,dest/'market.csv.gz')
    vintage=pd.read_csv(root/'outputs/vintage_checks.csv')
    vintage=vintage.loc[vintage.series_id.isin(SERIES)].copy()
    write_csv(vintage,dest/'vintages.csv.gz')
    metadata['market']={
        'name':'U.S. broad equity total return · French market factor plus risk-free rate',
        'url':'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html',
        'definition_url':'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_factors.html',
        'download_url':research['sources']['french'],
        'retrieved_at':research['retrieved_at'],'raw_sha256':digest,
        'raw_units':'Daily returns in percent','snapshot_start':str(market.date.min().date()),
        'snapshot_end':str(market.date.max().date()),
        'method':'Daily total return = Mkt-RF + RF. Wealth = cumulative product of 1 + return_pct/100. No S&P, Dow or price-only history is spliced in.',
        'classification':'Academic benchmark; value-weighted U.S. market, including distributions; revised history, not an investable index.'}
    metadata['vintages']={
        'name':'Bounded archived FRED/ALFRED as-of spot checks','retrieved_at':research['retrieved_at'],
        'url':'https://alfred.stlouisfed.org/',
        'method':'For each retained series/asof: FRED series/observations, realtime_start=asof, realtime_end=asof, observation_start=1776-07-04, observation_end=asof, sort_order=desc, limit=30. No revised fallback for absent archive data. PCE YoY uses exact prior-year archived index.',
        'raw_sha256':hashlib.sha256((root/'outputs/vintage_checks.csv').read_bytes()).hexdigest(),
        'caution':'Unavailable archive results do not prove a statistic was unpublished or unknowable.'}
    manifest={'schema_version':1,'built_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'snapshot_cutoff':'2024-12-31','classification':'Saved historical study; not a live market monitor',
              'sources':metadata,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.glob('*.csv.gz'))}}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Historical snapshot built:',len(market),'daily market returns;',sum(len(d) for d in macro),'macro observations;',len(vintage),'archive checks.')

if __name__=='__main__':
    main()
