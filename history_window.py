"""Shared display windows; legacy numeric values remain stable widget keys."""
import pandas as pd

HISTORY_YEARS = {365: 1, 730: 2, 1825: 5, 3650: 10, 7300: 20}
HISTORY_OPTIONS = [365, 730, 1825, 3650, 7300, 0]
HISTORY_LABELS = {**{days: f'{years} year' + ('s' if years != 1 else '') for days, years in HISTORY_YEARS.items()}, 0: 'All available'}

def today(now=None):
    value = pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    if value.tzinfo is not None:
        value = value.tz_convert('UTC').tz_localize(None)
    return value.normalize()

def history_start(days, now=None):
    if days == 0:
        return pd.Timestamp('1776-07-04')
    date = today(now)
    return date - pd.DateOffset(years=HISTORY_YEARS[days]) if days in HISTORY_YEARS else date - pd.Timedelta(days=days)

def clip_history(frame, days, date_column=None, now=None):
    dates = frame[date_column] if date_column else frame.index
    return frame.loc[(dates >= history_start(days, now)) & (dates <= today(now))].copy()
