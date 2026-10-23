"""Saved historical evidence and period-scoped calculations; no live substitutions."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math
import pandas as pd
from market_history_catalog import SERIES

DATA_DIR=Path(__file__).resolve().parent/'data/market_history'

@dataclass
class HistoryData:
    market: pd.DataFrame
    macro: pd.DataFrame
    vintages: pd.DataFrame
    manifest: dict


def load_history(root=DATA_DIR):
    root=Path(root)
    manifest=json.loads((root/'manifest.json').read_text())
    if set(manifest['files'])!={'market.csv.gz','macro.csv.gz','vintages.csv.gz'}:
        raise ValueError('Incomplete historical snapshot manifest.')
    for name,digest in manifest['files'].items():
        if name not in {'market.csv.gz','macro.csv.gz','vintages.csv.gz'}:
            raise ValueError('Unexpected historical snapshot file.')
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Historical snapshot integrity check failed.')
    market=pd.read_csv(root/'market.csv.gz',parse_dates=['date']).set_index('date').sort_index()
    macro=pd.read_csv(root/'macro.csv.gz',parse_dates=['date'])
    vintages=pd.read_csv(root/'vintages.csv.gz',parse_dates=['peak','asof','reference_date'])
    if market.index.duplicated().any() or macro.duplicated(['date','series_id']).any():
        raise ValueError('Duplicate observations in historical snapshot.')
    if not market.return_pct.map(math.isfinite).all() or (market.return_pct<=-100).any():
        raise ValueError('Invalid historical market returns.')
    if not macro.value.map(math.isfinite).all() or not set(macro.series_id)<=set(SERIES):
        raise ValueError('Invalid historical macro observations.')
    market['wealth']=(1+market.return_pct/100).cumprod()
    return HistoryData(market,macro,vintages,manifest)


def indicator_history(data,series):
    raw=data.macro.loc[data.macro.series_id==series,['date','value']].set_index('date').sort_index()
    if raw.empty:
        return raw
    if SERIES[series].transform=='yoy':
        raw=raw.asfreq('MS')
        prior=raw.value.shift(12).where(lambda v:v>0)
        raw['value']=(raw.value/prior-1)*100
    return raw


def reference_end(dates,series):
    """A month-start or quarter-start stamp is not a completed pre-event period."""
    frequency=SERIES[series].frequency
    if frequency=='monthly':
        return dates+pd.offsets.MonthEnd(0)
    if frequency=='quarterly':
        return dates+pd.offsets.QuarterEnd(0)
    return dates


def indicator_window(data,series,regime,pre_only=False):
    frame=indicator_history(data,series)
    end=pd.Timestamp(regime.start)-pd.Timedelta(days=1) if pre_only else pd.Timestamp(regime.view_end)
    frame=frame.loc[regime.view_start:end]
    if pre_only:
        frame=frame.loc[reference_end(frame.index,series)<=end]
    return frame


def slice_market(data,regime,pre_only=False):
    end=pd.Timestamp(regime.start)-pd.Timedelta(days=1) if pre_only else pd.Timestamp(regime.view_end)
    market=data.market.loc[regime.view_start:end].copy()
    if not market.empty:
        market['index_100']=100*market.wealth/market.wealth.iloc[0]
        market['drawdown_pct']=100*(market.wealth/market.wealth.cummax()-1)
    return market


def evidence_rows(data,regime,pre_only=False):
    """One row per selected series, using explicit windows and bounded staleness."""
    rows=[]
    start=pd.Timestamp(regime.start)
    end=pd.Timestamp(regime.end)
    for series in regime.indicators:
        definition=SERIES[series]
        full=indicator_history(data,series)
        before=full.loc[reference_end(full.index,series)<start].dropna()
        during=full.loc[start:end].dropna()
        budget={'daily':10,'weekly':21,'monthly':100,'quarterly':210}[definition.frequency]
        prior_date=before.index[-1] if not before.empty else None
        valid_prior=prior_date is not None and (start-prior_date).days<=budget
        rows.append({'Series':series,'Indicator':definition.name,'Unit':definition.unit,
                     'Role':definition.role,'Before stress':float(before.value.iloc[-1]) if valid_prior else None,
                     'Before reference date':prior_date.date().isoformat() if valid_prior else None,
                     'Before reference end':reference_end(pd.DatetimeIndex([prior_date]),series)[0].date().isoformat() if valid_prior else None,
                     'Stress minimum':float(during.value.min()) if not pre_only and not during.empty else None,
                     'Stress maximum':float(during.value.max()) if not pre_only and not during.empty else None,
                     'Coverage':'Available' if valid_prior else 'No comparable pre-period data',
                     'Source':data.manifest['sources'][series]['url']})
    return pd.DataFrame(rows)


def archived_rows(data,regime):
    if not regime.archive_peak:
        return pd.DataFrame()
    selected=data.vintages.loc[(data.vintages.peak==pd.Timestamp(regime.archive_peak)) &
                               data.vintages.series_id.isin(regime.indicators)].copy()
    if selected.empty:
        return selected
    selected['Indicator']=selected.series_id.map(lambda s:SERIES[s].name)
    selected['Archived value']=pd.to_numeric(selected.value,errors='coerce')
    selected['Unit']='Raw source level'
    for series in selected.series_id.unique():
        definition=SERIES[series]
        selected.loc[selected.series_id==series,'Unit']=('%' if series=='UNRATE' else
            definition.unit if definition.transform=='level' else data.manifest['sources'][series]['raw_units'])
    # Only PCE YoY was explicitly derived from the preserved archived indexes.
    mask=(selected.series_id=='PCEPI') & selected.yoy.notna()
    selected.loc[mask,'Archived value']=selected.loc[mask,'yoy']
    selected.loc[mask,'Unit']='% year over year'
    selected['Archive result']=selected.apply(lambda row:'Available' if row.status=='available' and pd.notna(row['Archived value']) else 'No usable archived observation',axis=1)
    selected['As of']=selected['asof'].dt.strftime('%Y-%m-%d')
    selected['Reference period']=selected.reference_date.dt.strftime('%Y-%m-%d')
    return selected[['As of','Indicator','Archived value','Unit','Reference period','Archive result','series_id']].sort_values(['As of','Indicator'])
