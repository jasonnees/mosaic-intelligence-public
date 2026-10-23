"""Source routing, transformations and freshness without UI or static fallbacks."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import pandas as pd
from risk_catalog import WATCH_RULES


def clean_frame(frame, series_id):
    if frame is None or frame.empty or not {'date', series_id} <= set(frame.columns):
        return pd.DataFrame(columns=['date', series_id])
    result = frame[['date', series_id]].copy()
    result['date'] = pd.to_datetime(result['date'], errors='coerce', utc=True).dt.tz_localize(None)
    result[series_id] = pd.to_numeric(result[series_id], errors='coerce')
    result = result.dropna()
    result = result.loc[result[series_id].map(math.isfinite).astype(bool)]
    return result.drop_duplicates('date', keep='last').sort_values('date').reset_index(drop=True)


def transform_frame(frame, indicator):
    """Match prior calendar-year periods, with bounded tolerance; never forward-fill gaps."""
    result = clean_frame(frame, indicator.series_id)
    if indicator.transform == 'level' or result.empty:
        return result
    tolerance = {'daily': 7, 'weekly': 7, 'monthly': 0, 'quarterly': 0}[indicator.frequency]
    previous = result.rename(columns={'date': 'prior_date', indicator.series_id: 'prior'})
    result['target'] = result['date'] - pd.DateOffset(years=1)
    result = pd.merge_asof(result.sort_values('target'), previous,
                           left_on='target', right_on='prior_date', direction='backward',
                           tolerance=pd.Timedelta(days=tolerance))
    denominator = result['prior'].where(result['prior'] > 0)
    result[indicator.series_id] = (result[indicator.series_id] / denominator - 1) * 100
    return result[['date', indicator.series_id]].reset_index(drop=True)


@dataclass
class Observation:
    value: float | None
    observed_at: str | None
    age_days: int | None
    status: str
    watch: str
    detail: str


def assess(frame, indicator, now=None):
    now = pd.Timestamp(now if now is not None else datetime.now(timezone.utc))
    if now.tzinfo is not None:
        now = now.tz_convert('UTC').tz_localize(None)
    raw = clean_frame(frame, indicator.series_id)
    if raw.empty:
        return Observation(None, None, None, 'missing', 'Unavailable', 'No usable observations')
    date = raw['date'].iloc[-1]
    age = (now.normalize() - date.normalize()).days
    transformed = transform_frame(raw, indicator)
    value = transformed[indicator.series_id].iloc[-1]
    value = float(value) if pd.notna(value) and math.isfinite(value) else None
    if age < 0:
        return Observation(None, date.date().isoformat(), age, 'invalid', 'Unavailable', 'Future-dated observation')
    if age > indicator.max_age_days:
        return Observation(value, date.date().isoformat(), age, 'stale', 'Unavailable', 'Observation exceeds the freshness budget')
    if value is None:
        return Observation(None, date.date().isoformat(), age, 'insufficient history', 'Unavailable', 'Prior-year comparison is missing or nonpositive')
    rule = WATCH_RULES.get(indicator.series_id)
    watch, detail = 'No fixed threshold', 'No fixed warning threshold assigned; use direction and series-specific guidance'
    if rule:
        operator, threshold, reason = rule
        # Arithmetic growth rates can place an exact boundary a few ulps above it.
        at_boundary = math.isclose(value, threshold, rel_tol=1e-12, abs_tol=1e-12)
        triggered = not at_boundary and (value > threshold if operator == 'gt' else value < threshold)
        watch = 'Watch' if triggered else 'Not triggered'
        condition = f'{operator} {threshold} {indicator.unit}'
        detail = (f'{reason}; value {value:.6g} {indicator.unit}; rule: {condition}' if triggered
                  else f'No rule breach; value {value:.6g} {indicator.unit}; watch condition: {reason} ({condition}). This is not an all-clear.')
    return Observation(value, date.date().isoformat(), age, 'fresh', watch, detail)


@dataclass
class FetchResult:
    frame: pd.DataFrame
    provenance: str
    fetched_at: str
    error: str = ''


class RiskDataService:
    """API first, optional S3 historical supplement; API wins overlapping dates."""
    def __init__(self, fred=None, eia=None, archive=None):
        self.fred = fred
        self.eia = eia
        self.archive = archive

    def fetch(self, indicator, lookback_days=730, now=None):
        from data_fetcher import FREDClient, EIAClient
        current = pd.Timestamp(now if now is not None else datetime.now(timezone.utc))
        start = current - pd.Timedelta(days=lookback_days)
        if indicator.transform == 'yoy':
            start -= pd.DateOffset(years=1)
            start -= pd.Timedelta(days=10)
        empty = pd.DataFrame(columns=['date', indicator.series_id])
        archive, live = empty, empty
        errors = []
        if self.archive is not None:
            try:
                if indicator.source == 'fred':
                    archive = self.archive.get_fred_series(indicator.series_id, full_history=True,
                                                          start_date=start.date().isoformat())
                else:
                    archive = self.archive.get_eia_series(indicator.series_id)
            except Exception:
                errors.append('Optional archive unavailable')
        try:
            if indicator.source == 'fred':
                client = self.fred if self.fred is not None else FREDClient()
                live = client.get_series(indicator.series_id, start_date=start.date().isoformat(),
                                         end_date=current.date().isoformat())
            elif indicator.source == 'eia':
                client = self.eia if self.eia is not None else EIAClient()
                live = client.get_series(indicator.series_id, days=(current - start).days)
            else:
                raise ValueError('Unsupported source')
        except Exception:
            # Exception text from requests can contain API keys in URLs.
            errors.append(f'{indicator.source.upper()} request failed; check key, connectivity or source availability')
        archive = clean_frame(archive, indicator.series_id)
        live = clean_frame(live, indicator.series_id)
        merged = clean_frame(pd.concat([archive, live], ignore_index=True), indicator.series_id)
        if not merged.empty:
            merged = merged[merged['date'] >= pd.Timestamp(start.date())].reset_index(drop=True)
        provenance = 'Unavailable'
        if not archive.empty:
            provenance = 'S3 archive'
        if not live.empty:
            provenance = f'{indicator.source.upper()} API' + (' + S3 history' if not archive.empty else '')
        return FetchResult(merged, provenance, current.isoformat(), '; '.join(errors))
