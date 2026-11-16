"""Exercise provider throttling, safe diagnostics and real history gaps offline."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

from data_fetcher import DataFetchError, FREDClient, source_error
from indicator_guidance import data_warning, direction
from risk_catalog import BY_ID
from risk_data import RiskDataService, assess
from scripts.audit_live_sources import main as audit_main


@pytest.fixture
def clock(monkeypatch):
    state = SimpleNamespace(now=0., sleeps=[])
    def sleep(seconds):
        state.sleeps.append(seconds)
        state.now += seconds
    monkeypatch.setattr('data_fetcher.time.monotonic', lambda: state.now)
    monkeypatch.setattr('data_fetcher.time.sleep', sleep)
    return state


def response(status=200, payload=None, retry_after=None):
    result = requests.Response()
    result.status_code = status
    result.url = 'https://api.stlouisfed.org/fred/series?api_key=private-key'
    result._content = json.dumps(payload if payload is not None else {}).encode()
    if retry_after is not None:
        result.headers['Retry-After'] = retry_after
    return result


def observations():
    return response(payload={'observations': [{'date': '2026-11-10', 'value': '4.2'}]})


def metadata():
    return response(payload={'seriess': [{key: 'test' for key in (
        'title', 'frequency', 'units', 'seasonal_adjustment', 'observation_end', 'last_updated')}]})


def test_metadata_and_observations_share_request_pacing(clock, monkeypatch):
    replies = iter([metadata(), observations()])
    calls = []
    def get(url, **kwargs):
        calls.append((clock.now, url, kwargs))
        return next(replies)
    monkeypatch.setattr('data_fetcher.requests.get', get)
    client = FREDClient('private-key')
    client.get_metadata('DGS10')
    result = client.get_series('DGS10')
    assert result.DGS10.tolist() == [4.2]
    assert [call[0] for call in calls] == [0, .6]
    assert all(call[2]['params']['api_key'] == 'private-key' for call in calls)


@pytest.mark.parametrize('status,header,delay', [(429, None, 60), (429, '90', 90),
    (503, '3', 3), (502, None, 1)])
def test_transient_failure_recovers_after_provider_cooldown(status, header, delay, clock, monkeypatch):
    replies = iter([response(status, retry_after=header), observations()])
    monkeypatch.setattr('data_fetcher.requests.get', lambda *a, **k: next(replies))
    client = FREDClient('private-key')
    assert client.get_series('DGS10').DGS10.tolist() == [4.2]
    assert delay in clock.sleeps
    assert client.request_diagnostics == {'attempts': 2, 'retries': 1, 'http_errors': {str(status): 1}}


def test_retry_after_http_date_is_respected(clock, monkeypatch):
    monkeypatch.setattr('data_fetcher.datetime', SimpleNamespace(
        now=lambda tz: datetime(2026, 11, 12, tzinfo=timezone.utc)))
    replies = iter([response(429, retry_after='Thu, 12 Nov 2026 00:01:30 GMT'), metadata()])
    monkeypatch.setattr('data_fetcher.requests.get', lambda *a, **k: next(replies))
    FREDClient('private-key').get_metadata('DGS10')
    assert 90 in clock.sleeps


@pytest.mark.parametrize('header', ['121', 'inf', 'NaN'])
def test_unbounded_retry_after_fails_without_retrying_early(header, clock, monkeypatch):
    calls = []
    def get(*a, **k):
        calls.append(1)
        return response(429, retry_after=header)
    monkeypatch.setattr('data_fetcher.requests.get', get)
    with pytest.raises(DataFetchError):
        FREDClient('private-key').get_metadata('DGS10')
    assert len(calls) == 1
    assert not clock.sleeps


@pytest.mark.parametrize('status,attempts', [(400, 1), (404, 1), (429, 3), (503, 3)])
def test_exhausted_and_permanent_errors_are_safe_and_remain_missing(status, attempts, clock, monkeypatch):
    monkeypatch.setattr('data_fetcher.requests.get', lambda *a, **k: response(status))
    client = FREDClient('private-key')
    result = RiskDataService(fred=client).fetch(BY_ID['DGS10'], now='2026-11-12')
    assert f'HTTP {status}' in result.error
    assert 'private-key' not in result.error and 'https://' not in result.error
    assert client.request_diagnostics['attempts'] == attempts
    assert assess(result.frame, BY_ID['DGS10'], '2026-11-12').status == 'missing'


def test_timeout_retries_are_bounded_and_sanitized(clock, monkeypatch):
    def get(*a, **k):
        raise requests.Timeout('https://example.org?api_key=private-key')
    monkeypatch.setattr('data_fetcher.requests.get', get)
    client = FREDClient('private-key')
    with pytest.raises(DataFetchError) as error:
        client.get_metadata('DGS10')
    assert client.request_diagnostics['attempts'] == 3
    assert 'timeout' in source_error('fred', error.value)
    assert 'private-key' not in str(error.value)


@pytest.mark.parametrize('payload', [{}, [], {'error_code': 400}, {'observations': [{'bad': 'shape'}]}])
def test_malformed_observations_fail_with_safe_diagnostics(payload, clock, monkeypatch):
    monkeypatch.setattr('data_fetcher.requests.get', lambda *a, **k: response(payload=payload))
    with pytest.raises(DataFetchError) as error:
        FREDClient('private-key').get_series('DGS10')
    assert 'invalid response' in source_error('fred', error.value)


def test_service_reuses_fred_client_across_series(clock, monkeypatch):
    monkeypatch.setattr('data_fetcher.config.FRED_API_KEY', 'private-key')
    monkeypatch.setattr('data_fetcher.requests.get', lambda *a, **k: observations())
    service = RiskDataService()
    service.fetch(BY_ID['DGS10'], now='2026-11-12')
    client = service.fred
    service.fetch(BY_ID['DGS10'], now='2026-11-12')
    assert service.fred is client
    assert client.request_diagnostics['attempts'] == 2
    assert .6 in clock.sleeps


@pytest.mark.parametrize('sid', ['CPIAUCSL', 'CPILFESL', 'CUSR0000SEHA'])
def test_october_2026_cpi_explains_missing_base_without_substitution(sid):
    values = pd.DataFrame({'date': ['2025-09-01', '2026-09-01', '2026-10-01'], sid: [100., 103., 104.]})
    result = assess(values, BY_ID[sid], '2026-11-12')
    assert result.status == 'insufficient history' and result.value is None
    assert '2025-10-01' in result.detail and 'BLS did not collect' in result.detail
    assert 'https://www.bls.gov/' in data_warning(result, BY_ID[sid])
    assert direction(values, BY_ID[sid], '2026-11-12').label == 'Not evaluated'
    # A real prior-year value restores calculation automatically.
    values.loc[len(values)] = ['2025-10-01', 100.]
    restored = assess(values, BY_ID[sid], '2026-11-12')
    assert restored.status == 'fresh' and restored.value == pytest.approx(4.)


def test_cpi_gap_explanation_does_not_mask_other_history_errors():
    for sid, dates, vals in [('CPIAUCSL', ['2025-10-01', '2026-10-01'], [0, 104]),
            ('PCEPI', ['2026-10-01'], [104]), ('CPIAUCSL', ['2026-09-01'], [104])]:
        result = assess(pd.DataFrame({'date': dates, sid: vals}), BY_ID[sid], '2026-11-12')
        assert result.status == 'insufficient history'
        assert 'BLS did not collect' not in result.detail


def test_audit_reports_recovered_throttle_and_keeps_stale_failures(clock, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr('config.FRED_API_KEY', 'private-key')
    monkeypatch.setattr('config.EIA_API_KEY', 'private-eia-key')
    monkeypatch.setattr('scripts.audit_live_sources.INDICATORS', [BY_ID['DGS10']])
    old_date = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    stale = response(payload={'observations': [{'date': old_date, 'value': '4.2'}]})
    replies = iter([response(429), metadata(), stale])
    monkeypatch.setattr('data_fetcher.requests.get', lambda *a, **k: next(replies))
    output = tmp_path / 'audit.json'
    monkeypatch.setattr('sys.argv', ['audit', '--strict', '--output', str(output)])
    assert audit_main() == 1
    report = json.loads(output.read_text())
    assert report['fred_requests']['http_errors'] == {'429': 1}
    assert report['series'][0]['observation']['status'] == 'stale'
    assert report['failures'] and report['status'] == 'failed'
    assert 'private-key' not in capsys.readouterr().out + output.read_text()
