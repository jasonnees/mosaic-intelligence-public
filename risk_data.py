"""Source routing, transformations and freshness without UI or static fallbacks."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import pandas as pd
from risk_catalog import WATCH_RULES, CASE_SHILLER_GRACE_DAYS, CASE_SHILLER_SOURCE, QUARTERLY_RELEASE_LAGS, QUARTERLY_GRACE_DAYS
from history_window import history_start


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


def freshness_context(indicator, observed_at):
    """Publication timing is series-specific; grace is an app assumption."""
    if indicator.series_id in QUARTERLY_RELEASE_LAGS and observed_at is not None:
        lag, source = QUARTERLY_RELEASE_LAGS[indicator.series_id]
        successor = pd.Timestamp(observed_at).to_period('Q') + 1
        expected = successor.end_time.normalize() + pd.Timedelta(days=lag)
        deadline = expected + pd.Timedelta(days=QUARTERLY_GRACE_DAYS)
        return {'method': 'quarterly publication budget',
                'next_update_expected': expected.date().isoformat(),
                'grace_calendar_days': QUARTERLY_GRACE_DAYS,
                'deadline': deadline.date().isoformat(), 'source_url': source,
                'assumption': 'Successor quarter end plus series-specific publication lag; not an official release date',
                'publication_lag_days': lag}
    if indicator.series_id != 'CSUSHPINSA' or observed_at is None:
        return {'method': 'observation age', 'max_age_days': indicator.max_age_days}
    reference = pd.Timestamp(observed_at).to_period('M').to_timestamp()
    # July's successor is August, published in October: +3 calendar months.
    release_month = reference + pd.DateOffset(months=3)
    month_end = release_month + pd.offsets.MonthEnd(0)
    release = month_end - pd.Timedelta(days=(month_end.weekday() - 1) % 7)
    deadline = release + pd.Timedelta(days=CASE_SHILLER_GRACE_DAYS)
    return {'method': 'expected monthly release', 'next_update_expected': release.date().isoformat(),
            'grace_calendar_days': CASE_SHILLER_GRACE_DAYS, 'deadline': deadline.date().isoformat(),
            'max_age_days': indicator.max_age_days, 'source_url': CASE_SHILLER_SOURCE}


def assess(frame, indicator, now=None, release=None):
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
    from release_timing import verified_release_context
    timing = verified_release_context(indicator, date, release, now) or freshness_context(indicator, date)
    overdue = (now.normalize() > pd.Timestamp(timing['deadline'])
               if 'deadline' in timing else age > indicator.max_age_days)
    if overdue:
        detail = (f'Next update budget ends {timing["next_update_expected"]}; '
                  f'{timing["grace_calendar_days"]}-day operational grace ended {timing["deadline"]}'
                  if 'deadline' in timing else 'Observation exceeds the freshness budget')
        return Observation(value, date.date().isoformat(), age, 'stale', 'Unavailable', detail)
    if value is None:
        prior = date - pd.DateOffset(years=1)
        detail = f'Prior-year comparison for {prior.date().isoformat()} is missing or nonpositive'
        if (indicator.series_id in {'CPIAUCSL', 'CPILFESL', 'CUSR0000SEHA'}
                and prior == pd.Timestamp('2025-10-01')
                and prior not in set(raw['date'])):
            detail += ('; BLS did not collect October 2025 CPI data during the federal shutdown. '
                       'Year-over-year inflation remains unavailable. BLS notice: '
                       'https://www.bls.gov/cpi/notices/2026/12m-changes-202610.htm')
        return Observation(None, date.date().isoformat(), age, 'insufficient history', 'Unavailable', detail)
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
    release: dict | None = None
    live_ok: bool | None = None


class RiskDataService:
    """API first, optional S3 historical supplement; API wins overlapping dates."""
    def __init__(self, fred=None, eia=None, archive=None):
        self.fred = fred
        self.eia = eia
        self.archive = archive

    def fetch(self, indicator, lookback_days=730, now=None):
        from data_fetcher import FREDClient, EIAClient, source_error
        current = pd.Timestamp(now if now is not None else datetime.now(timezone.utc))
        start = history_start(lookback_days, current)
        if indicator.transform == 'yoy' and lookback_days != 0:
            start -= pd.DateOffset(years=1)
            start -= pd.Timedelta(days=10)
        empty = pd.DataFrame(columns=['date', indicator.series_id])
        archive, live = empty, empty
        errors = []
        release = None
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
                if self.fred is None:
                    self.fred = FREDClient()
                live = self.fred.get_series(indicator.series_id, start_date=start.date().isoformat(),
                                         end_date=current.date().isoformat())
            elif indicator.source == 'eia':
                client = self.eia if self.eia is not None else EIAClient()
                live = client.get_series(indicator.series_id, days=(pd.Timestamp(current.date()) - start).days)
            else:
                raise ValueError('Unsupported source')
        except Exception as error:
            # Exception text from requests can contain API keys in URLs.
            errors.append(source_error(indicator.source, error))
        archive = clean_frame(archive, indicator.series_id)
        live = clean_frame(live, indicator.series_id)
        if not live.empty:
            # Archives supplement history only, never override the API's latest period.
            archive = archive[archive['date'] < live['date'].min()]
        if indicator.series_id == 'ELEC.PRICE.US-RES.M' and not live.empty:
            try:
                release = client.get_release_calendar()
                if not isinstance(release, dict):
                    release = None
            except Exception:
                errors.append('EIA release calendar unavailable; using observation-age budget')
        merged = clean_frame(pd.concat([archive, live], ignore_index=True), indicator.series_id)
        if not merged.empty:
            merged = merged[merged['date'] >= pd.Timestamp(start.date())].reset_index(drop=True)
        provenance = 'Unavailable'
        if not archive.empty:
            provenance = 'S3 archive'
        if not live.empty:
            provenance = f'{indicator.source.upper()} API' + (' + S3 history' if not archive.empty else '')
        return FetchResult(merged, provenance, current.isoformat(), '; '.join(errors), release, not live.empty)


def assess_result(result, indicator, now=None):
    observation = assess(result.frame, indicator, now, release=result.release)
    if result.live_ok is False and observation.status not in {'missing', 'invalid', 'stale'}:
        return Observation(observation.value, observation.observed_at, observation.age_days,
                           'unverified', 'Unavailable',
                           'Live source unavailable; archive history cannot establish current data health')
    return observation


def result_freshness_context(result, indicator, observed_at, now=None):
    from release_timing import verified_release_context
    return (verified_release_context(indicator, observed_at, result.release,
                                     now if now is not None else datetime.now(timezone.utc))
            or freshness_context(indicator, observed_at))
