from dataclasses import replace
from unittest.mock import Mock, patch
import pandas as pd
import pytest

from risk_catalog import BY_ID
from risk_data import FetchResult, RiskDataService, assess_result, result_freshness_context
from indicator_guidance import data_warning, direction
from release_timing import parse_eia_release

SID = 'ELEC.PRICE.US-RES.M'
HEADER = '<h2>Data for August 2026</h2> Release Date: <b>October 23, 2026</b> Next Release Date: November 24, 2026'


def result(period='2026-08-01', release=None):
    return FetchResult(pd.DataFrame({'date': ['2026-05-01', period], SID: [17., 18.16]}),
                       'EIA API', '2026-11-10T19:00:00+00:00',
                       release=release, live_ok=True)


def test_current_electricity_release_uses_publisher_dates_not_reference_age():
    fetched = result(release=parse_eia_release(HEADER))
    observation = assess_result(fetched, BY_ID[SID], '2026-11-10')
    assert observation.age_days == 101
    assert observation.status == 'fresh'
    assert observation.value == 18.16
    assert BY_ID[SID].max_age_days == 100  # Generic budget remains unchanged.
    context = result_freshness_context(fetched, BY_ID[SID], observation.observed_at, '2026-11-10')
    assert context['published_at'] == '2026-10-23'
    assert context['deadline'] == '2026-12-01'
    assert direction(fetched.frame, BY_ID[SID], '2026-11-10', observation).label == 'Rising'
    assert assess_result(fetched, BY_ID[SID], '2026-12-01').status == 'fresh'
    overdue = assess_result(fetched, BY_ID[SID], '2026-12-02')
    assert overdue.status == 'stale' and overdue.watch == 'Unavailable'
    assert '2026-12-01' in data_warning(overdue, BY_ID[SID])


@pytest.mark.parametrize('change', [
    {'period': '2026-09-01'}, {'published_at': '2026-11-11'},
    {'next_release': '2026-10-22'}, {'next_release': '2028-01-01'},
    {'source_url': 'https://example.com'}, {'published_at': 'bad'},
    {'published_at': None}, {'period': 'NaT'},
])
def test_unverified_calendar_cannot_clear_stale(change):
    calendar = parse_eia_release(HEADER) | change
    observation = assess_result(result(release=calendar), BY_ID[SID], '2026-11-10')
    assert observation.status == 'stale' and observation.watch == 'Unavailable'


def test_old_period_missing_calendar_and_future_observations_fail_closed():
    assert assess_result(result(), BY_ID[SID], '2026-11-10').status == 'stale'
    fetched = result('2026-07-01', parse_eia_release(HEADER))
    assert assess_result(fetched, BY_ID[SID], '2026-11-10').status == 'stale'
    assert assess_result(result('2026-12-01', parse_eia_release(HEADER)), BY_ID[SID], '2026-11-10').status == 'invalid'
    with pytest.raises(ValueError):
        parse_eia_release('<html>Access denied</html>')


def test_service_fetches_release_evidence_and_handles_calendar_failure():
    client = Mock()
    client.get_series.return_value = result().frame
    client.get_release_calendar.return_value = parse_eia_release(HEADER)
    service = RiskDataService(eia=client)
    fetched = service.fetch(BY_ID[SID], 730, '2026-11-10')
    assert assess_result(fetched, BY_ID[SID], '2026-11-10').status == 'fresh'
    client.get_release_calendar.side_effect = RuntimeError('api_key=secret')
    fetched = service.fetch(BY_ID[SID], 730, '2026-11-10')
    assert assess_result(fetched, BY_ID[SID], '2026-11-10').status == 'stale'
    assert 'secret' not in fetched.error


def test_recent_archive_after_api_failure_cannot_clear_watch_or_show_direction():
    archive, fred = Mock(), Mock()
    archive.get_fred_series.return_value = pd.DataFrame({'date': ['2026-11-09'], 'VIXCLS': [19.]})
    fred.get_series.side_effect = RuntimeError('offline')
    fetched = RiskDataService(fred=fred, archive=archive).fetch(BY_ID['VIXCLS'], 730, '2026-11-10')
    observation = assess_result(fetched, BY_ID['VIXCLS'], '2026-11-10')
    assert observation.status == 'unverified' and observation.watch == 'Unavailable'
    assert direction(fetched.frame, BY_ID['VIXCLS'], '2026-11-10', observation).label == 'Not evaluated'


def test_archive_tail_does_not_impersonate_latest_api_observation():
    archive, fred = Mock(), Mock()
    archive.get_fred_series.return_value = pd.DataFrame({'date': ['2026-10-01', '2026-11-10'], 'VIXCLS': [20., 15.]})
    fred.get_series.return_value = pd.DataFrame({'date': ['2026-11-09'], 'VIXCLS': [31.]})
    fetched = RiskDataService(fred=fred, archive=archive).fetch(BY_ID['VIXCLS'], 730, '2026-11-10')
    assert fetched.frame['VIXCLS'].tolist() == [20., 31.]
    assert assess_result(fetched, BY_ID['VIXCLS'], '2026-11-10').watch == 'Watch'


@pytest.mark.parametrize('sid', ['CPIAUCSL', 'CPILFESL', 'CUSR0000SEHA'])
def test_cpi_missing_october_base_explained_without_filling_or_clearing(sid):
    frame = pd.DataFrame({'date': ['2025-09-01', '2026-09-01', '2026-10-01'], sid: [100., 103., 104.]})
    fetched = FetchResult(frame, 'FRED API', '2026-11-10', live_ok=True)
    observation = assess_result(fetched, BY_ID[sid], '2026-11-10')
    assert observation.status == 'insufficient history' and observation.value is None
    assert 'October 2025' in data_warning(observation, BY_ID[sid])
    assert 'BLS notice:' in data_warning(observation, BY_ID[sid])
    restored = pd.concat([frame, pd.DataFrame({'date': ['2025-10-01'], sid: [101.]})])
    assert assess_result(replace(fetched, frame=restored), BY_ID[sid], '2026-11-10').status == 'fresh'


def test_app_uses_publisher_evidence_for_table_direction_and_chart():
    from pathlib import Path
    from datetime import datetime, timezone
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    st.cache_data.clear()
    fetched = result(release=parse_eia_release(HEADER))
    def source(self, indicator, *args, **kwargs):
        if indicator.series_id == SID:
            return fetched
        return FetchResult(pd.DataFrame(columns=['date', indicator.series_id]), 'Unavailable', 'fixture', live_ok=False)
    original = st.dataframe
    def choose_electricity(data, **kwargs):
        original(data, **kwargs)
        rows = data.data if hasattr(data, 'data') else data
        indices = [n for n, sid in enumerate(rows['Series']) if sid == SID]
        return {'selection': {'rows': indices}}
    with patch('risk_data.RiskDataService.fetch', source), patch('risk_data.datetime') as clock, patch('streamlit.dataframe', side_effect=choose_electricity):
        clock.now.return_value = datetime(2026, 11, 10, tzinfo=timezone.utc)
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30).run()
        app.sidebar.radio[0].set_value('Inflation risk').run()
        assert not app.exception
        row = app.dataframe[0].value.query('Series == @SID').iloc[0]
        assert row['Data status'] == 'fresh' and row['Direction'] == 'Rising'
        assert row['Publication deadline'] == '2026-12-01'
        assert any('Publisher release date: 2026-10-23' in c.value for c in app.caption)
        assert len(app.get('plotly_chart')) == 1
    st.cache_data.clear()
