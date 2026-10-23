"""Annual, rebalanced historical portfolio scenarios. No forecasts or fitted rules."""
import hashlib
import json
from pathlib import Path
import math
import pandas as pd

ASSETS = {'stocks': 'US large-cap stocks', 'treasuries': '10-year Treasuries', 'cash': 'Treasury bills / cash'}
SCENARIOS = {
    'Great Depression · 1929–1932': (1929, 1932, 'Equity losses persisted across several calendar years. Deflation changed the purchasing-power result.'),
    'Oil shock · 1973–1974': (1973, 1974, 'Inflation eroded cash purchasing power while equities fell. Compare nominal and inflation-adjusted outcomes.'),
    'Volcker tightening · 1980–1982': (1980, 1982, 'High inflation and changing interest rates tested both stock and bond exposure.'),
    'Dot-com bust · 2000–2002': (2000, 2002, 'Three down years in large-cap stocks tested the ability to wait through a prolonged decline.'),
    'Financial crisis · 2007–2009': (2007, 2009, 'Treasury gains cushioned the stock collapse in 2008; the 2009 rebound did not erase every portfolio’s loss.'),
    'Pandemic · 2020': (2020, 2020, 'Positive full-year returns conceal the severe intra-year crash. Use Market history for the daily equity path.'),
    'Inflation & rate shock · 2022': (2022, 2022, 'Stocks and 10-year Treasuries both lost value. This tests whether a bond allocation actually cushioned the shock.'),
}
DATA = Path(__file__).resolve().parent / 'data/portfolio_history'

def load_history(root=DATA):
    metadata = json.loads((root / 'manifest.json').read_text())
    payload = (root / 'returns.csv').read_bytes()
    if hashlib.sha256(payload).hexdigest() != metadata['csv_sha256']:
        raise ValueError('Historical return snapshot failed its integrity check.')
    data = pd.read_csv(root / 'returns.csv').set_index('year')
    if data.index.tolist() != list(range(metadata['first_year'], metadata['last_year'] + 1)) or not data.apply(lambda column: column.map(math.isfinite)).all().all():
        raise ValueError('Historical return coverage is incomplete.')
    return data, metadata

def simulate(data, weights, start, end, balance=100_000, real=False):
    if set(weights) != set(ASSETS) or any(not math.isfinite(w) or w < 0 or w > 100 for w in weights.values()) or not math.isclose(sum(weights.values()), 100, abs_tol=1e-8):
        raise ValueError('Allocation must total 100%, with each asset between 0% and 100%.')
    if not math.isfinite(balance) or balance <= 0 or end < start:
        raise ValueError('Enter a positive starting balance and a valid year window.')
    # Continue after the scenario to measure recovery, without resetting at its end.
    frame = data.loc[start:].copy()
    needed = [a for a, w in weights.items() if w > 0] + (['inflation'] if real else [])
    if start not in frame.index or end not in frame.index or frame.index.tolist() != list(range(start, int(frame.index.max()) + 1)) or frame[needed].isna().any().any() or not frame[needed].apply(lambda column: column.map(math.isfinite)).all().all():
        raise ValueError('Missing annual observations for the selected allocation or period.')
    if (frame[needed] <= -1).any().any():
        raise ValueError('Invalid return in the selected history.')
    contributions = pd.DataFrame({a: frame[a] * w / 100 if w else 0.0 for a, w in weights.items()}, index=frame.index)
    nominal = contributions.sum(axis=1)
    returns = (1 + nominal) / (1 + frame.inflation) - 1 if real else nominal
    if (returns <= -1).any():
        raise ValueError('Invalid return in the selected history.')
    wealth = pd.concat([pd.Series({start - 1: float(balance)}), balance * (1 + returns).cumprod()])
    scope = wealth.loc[:end]
    drawdown = scope / scope.cummax() - 1
    peak = trough = recovery = None
    if drawdown.min() < -1e-12:
        trough = int(drawdown.idxmin())
        peak = int(scope.loc[:trough].idxmax())
        recovered = wealth.loc[trough + 1:]
        recovered = recovered[recovered >= wealth.loc[peak] - 1e-8]
        recovery = int(recovered.index[0]) if len(recovered) else None
    return {'wealth': wealth, 'returns': returns, 'contributions': contributions,
            'period_return': scope.iloc[-1] / balance - 1, 'drawdown': float(drawdown.min()),
            'peak': peak, 'trough': trough, 'recovery': recovery,
            'worst_year': float(returns.loc[start:end].min()),
            'worst_year_date': int(returns.loc[start:end].idxmin()),
            'ending_year': end, 'ending_value': float(scope.loc[end]),
            'year_end_drawdown': drawdown}
