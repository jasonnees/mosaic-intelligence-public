"""Publisher evidence for release timing; never infer freshness from HTTP success."""
from html import unescape
import re
import pandas as pd
import requests

EIA_RELEASE_URL = 'https://www.eia.gov/electricity/monthly/'
CENSUS_RELEASE_URL = 'https://www.census.gov/mtis/current/index.html'
CENSUS_SCHEDULE_URL = 'https://www.census.gov/mtis/release_schedule.html'


def parse_census_release(current_text, schedule_text):
    """Match the current publication to its successor data month in the schedule."""
    current = ' '.join(unescape(re.sub(r'<[^>]+>', ' ', current_text)).split())
    schedule = ' '.join(unescape(re.sub(r'<[^>]+>', ' ', schedule_text)).split())
    period = re.search(r'Manufacturing and Trade Inventories and Sales:\s*([A-Za-z]+ \d{4})', current)
    published = re.search(r'FOR IMMEDIATE RELEASE:\s*[A-Za-z]+,\s*([A-Za-z]+ \d{1,2}, \d{4})', current)
    if not period or not published:
        raise ValueError('Census current publication unavailable')
    period = pd.Timestamp(period.group(1))
    successor = (period + pd.DateOffset(months=1)).strftime('%B %Y')
    expected = re.search(re.escape(successor) + r'\s+([A-Za-z]+ \d{1,2}, \d{4})', schedule)
    if not expected:
        raise ValueError('Census successor release unavailable')
    return {'period': period.date().isoformat(),
            'published_at': pd.Timestamp(published.group(1)).date().isoformat(),
            'next_release': pd.Timestamp(expected.group(1)).date().isoformat(),
            'source_url': CENSUS_RELEASE_URL, 'schedule_url': CENSUS_SCHEDULE_URL}


def get_census_release_calendar():
    pages = []
    for url in (CENSUS_RELEASE_URL, CENSUS_SCHEDULE_URL):
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        pages.append(response.text)
    return parse_census_release(*pages)


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
    source = {'ELEC.PRICE.US-RES.M': EIA_RELEASE_URL,
              'ISRATIO': CENSUS_RELEASE_URL}.get(indicator.series_id)
    if source is None or not isinstance(release, dict):
        return None
    if indicator.series_id == 'ISRATIO' and release.get('schedule_url') != CENSUS_SCHEDULE_URL:
        return None
    try:
        period = pd.Timestamp(release['period'])
        published = pd.Timestamp(release['published_at'])
        expected = pd.Timestamp(release['next_release'])
        today = pd.Timestamp(now).date()
        if (release['source_url'] != source or pd.isna(period)
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
            'grace_calendar_days': 7, 'source_url': source,
            **({'schedule_url': CENSUS_SCHEDULE_URL} if indicator.series_id == 'ISRATIO' else {})}
