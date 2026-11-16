"""Regression checks for the November monitoring failures, with no live feeds."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from data_fetcher import get_fred_client
from release_timing import parse_census_release, verified_release_context
from risk_catalog import BY_ID, INDICATORS
from risk_data import FetchResult, RiskDataService, assess_result
from scripts.audit_live_sources import audit_failures, classify_row, main

CURRENT = '''<h4>FOR IMMEDIATE RELEASE: Thursday, October 15, 2026</h4>
<h2>Manufacturing and Trade Inventories and Sales: August 2026</h2>'''
SCHEDULE = '''<table><tr><td>September 2026</td><td>November 17, 2026</td></tr>
<tr><td>October 2026</td><td>December 16, 2026</td></tr></table>'''


@pytest.fixture
def shared_client(monkeypatch):
    monkeypatch.setattr('data_fetcher._fred_clients', {})
    monkeypatch.setattr('config.FRED_API_KEY', 'test-shared-key')
    monkeypatch.setattr('config.EIA_API_KEY', 'test-eia-key')
    monkeypatch.setattr('config.BEA_API_KEY', '')
    monkeypatch.setattr('config.DATA_SOURCE_MODE', 'api')
    clock = SimpleNamespace(now=0., calls=[])
    monkeypatch.setattr('data_fetcher.time', SimpleNamespace(
        monotonic=lambda: clock.now,
        sleep=lambda delay: setattr(clock, 'now', clock.now + delay)))
    return clock


def test_concurrent_cold_start_constructs_one_client_and_paces_all_requests(shared_client, monkeypatch):
    from tests.test_fred_reliability import observations
    def get(*args, **kwargs):
        shared_client.calls.append(shared_client.now)
        return observations()
    monkeypatch.setattr('data_fetcher.requests.get', get)
    def fetch(_):
        client = get_fred_client()
        client.get_series('DGS10')
        return client
    with ThreadPoolExecutor(max_workers=16) as pool:
        clients = list(pool.map(fetch, range(130)))
    assert all(client is clients[0] for client in clients)
    gaps = [b-a for a,b in zip(shared_client.calls, shared_client.calls[1:])]
    assert min(gaps) >= .6 - 1e-9
    assert clients[0].request_diagnostics['attempts'] == 130
    assert get_fred_client('different-key') is not clients[0]


def test_census_current_month_successor_and_expiry():
    release = parse_census_release(CURRENT, SCHEDULE)
    fetched = FetchResult(pd.DataFrame({'date': ['2026-08-01'], 'ISRATIO': [1.33]}),
                          'FRED API', 'fixture', release=release, live_ok=True)
    assert release['next_release'] == '2026-11-17'
    for now in ['2026-11-15', '2026-11-17', '2026-11-24']:
        assert assess_result(fetched, BY_ID['ISRATIO'], now).status == 'fresh'
    assert assess_result(fetched, BY_ID['ISRATIO'], '2026-11-25').status == 'stale'
    assert assess_result(replace(fetched, release=None), BY_ID['ISRATIO'], '2026-11-15').status == 'stale'
    assert assess_result(replace(fetched, live_ok=False), BY_ID['ISRATIO'], '2026-11-15').status == 'unverified'


@pytest.mark.parametrize('change', [
    {'period': '2026-07-01'}, {'published_at': '2026-11-16'},
    {'next_release': '2026-10-14'}, {'next_release': '2027-01-01'},
    {'source_url': 'https://example.com'}, {'schedule_url': None},
    {'period': 'NaT'}, {'published_at': 'bad'},
])
def test_census_invalid_evidence_does_not_extend_budget(change):
    release = parse_census_release(CURRENT, SCHEDULE) | change
    assert verified_release_context(BY_ID['ISRATIO'], '2026-08-01', release, '2026-11-15') is None


def test_census_parser_rejects_missing_publication_or_successor():
    with pytest.raises(ValueError):
        parse_census_release('<html>Access denied</html>', SCHEDULE)
    with pytest.raises(ValueError):
        parse_census_release(CURRENT, SCHEDULE.replace('September 2026', 'August 2026'))


@pytest.mark.parametrize('sid', ['CPIAUCSL', 'CPILFESL', 'CUSR0000SEHA'])
def test_known_gap_warns_but_cannot_mask_outages_other_gaps_or_overdue_observations(sid):
    frame = pd.DataFrame({'date': ['2025-09-01', '2026-09-01', '2026-10-01'], sid: [100., 103., 104.]})
    fetched = FetchResult(frame, 'FRED API', 'fixture', live_ok=True)
    row = {'series_id': sid, 'provenance': fetched.provenance,
           'observation': asdict(assess_result(fetched, BY_ID[sid], '2026-11-15'))}
    assert not audit_failures([row], [sid])
    assert classify_row(row)['known_limitation']
    assert row['observation']['value'] is None and row['observation']['watch'] == 'Unavailable'
    for change in [{'error': 'HTTP 429 exhausted'}, {'metadata_error': 'HTTP 400'},
                   {'live_ok': False}, {'provenance': 'S3 archive'}]:
        assert audit_failures([row | change], [sid])
    overdue = row | {'observation': asdict(assess_result(fetched, BY_ID[sid], '2027-02-01'))}
    assert audit_failures([overdue], [sid])
    for base in [0., -1., 101.]:
        restored = pd.concat([frame, pd.DataFrame({'date': ['2025-10-01'], sid: [base]})])
        obs = assess_result(replace(fetched, frame=restored), BY_ID[sid], '2026-11-15')
        assert obs.known_limitation is None
        assert bool(audit_failures([row | {'observation': asdict(obs)}], [sid])) == (base <= 0)


def test_observation_mode_skips_metadata_and_preserves_warning_summary(monkeypatch, tmp_path, capsys):
    sid = 'CPIAUCSL'
    frame = pd.DataFrame({'date': ['2026-10-01'], sid: [104.]})
    fetched = FetchResult(frame, 'FRED API', 'fixture', live_ok=True)
    monkeypatch.setattr('config.FRED_API_KEY', 'private-key')
    monkeypatch.setattr('config.EIA_API_KEY', 'private-key')
    monkeypatch.setattr('scripts.audit_live_sources.INDICATORS', [BY_ID[sid]])
    monkeypatch.setattr('risk_data.datetime', SimpleNamespace(now=lambda tz: datetime(2026,11,15,tzinfo=timezone.utc)))
    monkeypatch.setattr('risk_data.RiskDataService.fetch', lambda *a, **k: fetched)
    def unexpected(*args):
        pytest.fail('Observation-only audit must not request metadata')
    monkeypatch.setattr('data_fetcher.FREDClient.get_metadata', unexpected)
    output, summary = tmp_path/'audit.json', tmp_path/'summary.md'
    monkeypatch.setattr('sys.argv', ['audit', '--strict', '--observations-only', '--output', str(output), '--summary', str(summary)])
    assert main() == 0
    report = json.loads(output.read_text())
    assert report['status'] == 'passed_with_warnings' and report['warnings']
    assert report['series'][0]['metadata_status'] == 'not_checked'
    assert 'insufficient history' in summary.read_text()
    assert 'private-key' not in output.read_text() + summary.read_text() + capsys.readouterr().out


def test_cold_all_views_share_actual_fred_transport(shared_client, monkeypatch):
    """Render configured views through real loaders with synthetic HTTP responses."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from macro_components import CPI_GROUPS, CPI_DETAIL, GDP_FRED
    from tests.test_fred_reliability import response
    st.cache_data.clear()
    st.cache_resource.clear()
    calls = []
    def get(url, **kwargs):
        sid = kwargs['params']['series_id']
        calls.append(sid)
        frequency = BY_ID[sid].frequency if sid in BY_ID else ('quarterly' if sid in GDP_FRED.values() else 'monthly')
        freq = {'daily':'D', 'weekly':'W', 'monthly':'MS', 'quarterly':'QS'}[frequency]
        dates = pd.date_range('2023-01-01', pd.Timestamp.now().normalize(), freq=freq)
        return response(payload={'observations': [{'date': str(date.date()), 'value': str(100 + n/20)}
                                                 for n,date in enumerate(dates)]})
    monkeypatch.setattr('data_fetcher.requests.get', get)
    monkeypatch.setattr('release_timing.get_census_release_calendar', lambda: parse_census_release(CURRENT, SCHEDULE))
    sid = 'ELEC.PRICE.US-RES.M'
    monkeypatch.setattr('data_fetcher.EIAClient.get_series', lambda *a, **k:
                        pd.DataFrame({'date': [pd.Timestamp.now().normalize()], sid: [18.]}))
    monkeypatch.setattr('data_fetcher.EIAClient.get_release_calendar', lambda *a: None)
    try:
        root = Path(__file__).resolve().parents[1]
        app = AppTest.from_file(str(root/'app.py'), default_timeout=30).run()
        for view in json.loads((root/'monitoring.json').read_text())['chart_views']:
            app.sidebar.radio[0].set_value(view).run()
            assert not app.exception, view
            assert app.get('plotly_chart'), view
        expected = {i.series_id for i in INDICATORS if i.source == 'fred'} | set(CPI_GROUPS) | set(CPI_DETAIL) | set(GDP_FRED.values())
        assert expected <= set(calls)
        assert get_fred_client().request_diagnostics['attempts'] == len(calls)
    finally:
        st.cache_data.clear()
        st.cache_resource.clear()


def test_dashboard_separates_known_gaps_from_actionable_data_issues(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    st.cache_data.clear()
    st.cache_resource.clear()
    monkeypatch.setattr('risk_data.datetime', SimpleNamespace(now=lambda tz: datetime(2026,11,15,tzinfo=timezone.utc)))
    def fetch(self, indicator, *args, **kwargs):
        sid = indicator.series_id
        dates = ['2025-11-14', '2026-11-14']
        if sid == 'CPIAUCSL':
            dates = ['2025-09-01', '2026-10-01']
        elif sid == 'UNRATE':
            dates = ['2024-01-01', '2025-01-01']
        elif sid == 'HOUST':
            return FetchResult(pd.DataFrame(columns=['date', sid]), 'Unavailable', 'fixture',
                               error='FRED request failed (HTTP 503)', live_ok=False)
        return FetchResult(pd.DataFrame({'date': dates, sid: [100., 104.]}), 'FRED API', 'fixture', live_ok=True)
    monkeypatch.setattr('risk_data.RiskDataService.fetch', fetch)
    try:
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=30).run()
        assert not app.exception
        metrics = {m.label: m.value for m in app.metric}
        assert metrics['Fresh readings'] == '10/13'
        assert metrics['Data issues'] == '2'
        assert metrics['Known gaps'] == '1'
        assert any('12/13' in c.value for c in app.caption)
        picker = next(r for r in app.radio if r.label == 'Filter observations')
        picker.set_value('Needs attention').run()
        assert set(app.dataframe[0].value.Series) == {'UNRATE', 'HOUST'}
        next(r for r in app.radio if r.label == 'Filter observations').set_value('Known gaps').run()
        row = app.dataframe[0].value.iloc[0]
        assert row.Series == 'CPIAUCSL' and pd.isna(row.Value)
        assert row['Feed status'] == 'Available' and row['Watch condition'] == 'Unavailable'
        assert any('Known source limitation' in item.value for item in app.info)
        assert any(m.label == 'Latest reading' and m.value == 'Unavailable' for m in app.metric)
    finally:
        st.cache_data.clear()
        st.cache_resource.clear()
