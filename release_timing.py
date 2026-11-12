"""Publisher evidence for release timing; never infer freshness from HTTP success."""
from html import unescape
import re
import pandas as pd

EIA_RELEASE_URL = 'https://www.eia.gov/electricity/monthly/'


def parse_eia_release(text):
    text = unescape(re.sub(r'<[^>]+>', ' ', text))
    text = ' '.join(text.split())
    match = re.search(
        r'Data for ([A-Za-z]+ \d{4})\s+Release Date:\s*([A-Za-z]+ \d{1,2}, \d{4})'
        r'\s+Next Release Date:\s*([A-Za-z]+ \d{1,2}, \d{4})', text, re.I)
    if not match:
        raise ValueError('EIA release dates unavailable')
    period, published, expected = (pd.Timestamp(value) for value in match.groups())
    return {'period': period.date().isoformat(), 'published_at': published.date().isoformat(),
            'next_release': expected.date().isoformat(), 'source_url': EIA_RELEASE_URL}


def verified_release_context(indicator, observed_at, release, now):
    """Use only matching, plausible publisher evidence; otherwise keep the age budget."""
    if indicator.series_id != 'ELEC.PRICE.US-RES.M' or not isinstance(release, dict):
        return None
    try:
        period = pd.Timestamp(release['period'])
        published = pd.Timestamp(release['published_at'])
        expected = pd.Timestamp(release['next_release'])
        today = pd.Timestamp(now).date()
        if (release['source_url'] != EIA_RELEASE_URL or pd.isna(period)
                or pd.isna(published) or pd.isna(expected)
                or period != pd.Timestamp(observed_at)
                or period.day != 1 or published.date() > today
                or not 0 <= (published - period).days <= 100
                or not 1 <= (expected - published).days <= 62):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return {'method': 'publisher release calendar',
            'published_at': published.date().isoformat(),
            'next_update_expected': expected.date().isoformat(),
            'deadline': (expected + pd.Timedelta(days=7)).date().isoformat(),
            'grace_calendar_days': 7, 'source_url': EIA_RELEASE_URL}
