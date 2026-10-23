"""Build the public annual-return snapshot from Damodaran's downloaded workbook.
Usage: python scripts/build_portfolio_history.py /path/to/histretSP.xls
Requires pandas and xlrd for this build step only; runtime reads CSV.
"""
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import pandas as pd

SOURCE = 'https://www.stern.nyu.edu/~adamodar/pc/datasets/histretSP.xls'

def build(source, target):
    raw = Path(source).read_bytes()
    updated = pd.read_excel(source, sheet_name='Returns by year', header=None).iloc[0, 1]
    table = pd.read_excel(source, sheet_name='Returns by year', header=19)
    assert list(table.columns[:5]) == ['Year', 'S&P 500 (includes dividends)', 'US Small cap (bottom decile)', '3-month T.Bill', 'US T. Bond (10-year)']
    years = pd.to_numeric(table['Year'], errors='coerce')
    table = table.loc[years.between(1928, 2100)].copy()
    result = pd.DataFrame({'year': table['Year'].astype(int), 'stocks': table.iloc[:, 1], 'treasuries': table.iloc[:, 4], 'cash': table.iloc[:, 3]})
    real = pd.read_excel(source, sheet_name='Nominal vs Real Data', header=0)
    real = real.loc[pd.to_numeric(real['Year'], errors='coerce').between(1928, 2100)]
    inflation = real.set_index('Year')['Inflation Rate']
    result['inflation'] = result.year.map(inflation)
    result = result.sort_values('year').reset_index(drop=True)
    assert result.year.tolist() == list(range(1928, int(result.year.max()) + 1))
    assert result.notna().all().all()
    target.mkdir(parents=True, exist_ok=True)
    payload = result.to_csv(index=False).encode()
    (target / 'returns.csv').write_bytes(payload)
    metadata = {'source_url': SOURCE, 'source_notes': 'https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html',
                'source_updated': updated.strftime('%Y-%m-%d'), 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                'workbook_sha256': hashlib.sha256(raw).hexdigest(), 'csv_sha256': hashlib.sha256(payload).hexdigest(),
                'first_year': int(result.year.min()), 'last_year': int(result.year.max()), 'frequency': 'calendar year',
                'units': 'decimal annual return; inflation is December-over-December CPI change',
                'sheets': ['Returns by year', 'Nominal vs Real Data'],
                'stocks': 'S&P 500 including dividends; backfilled large-cap indexes before 1957.',
                'treasuries': 'Damodaran modeled constant-maturity 10-year Treasury return: coupon and repricing; not a fund return.',
                'cash': 'Average 3-month Treasury bill rate during each year; an approximation of cash earnings.',
                'inflation': 'CPI-U not seasonally adjusted; workbook annual inflation series.'}
    (target / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')

if __name__ == '__main__':
    build(sys.argv[1], Path(__file__).resolve().parents[1] / 'data/portfolio_history')
