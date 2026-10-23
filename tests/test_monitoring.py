import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from scripts.audit_live_sources import audit_failures, main as audit_main
from scripts.check_deployment import check_http, load_target, main as deployment_main


def test_target_requires_explicit_deployment_and_valid_urls(tmp_path):
    path = tmp_path / 'monitoring.json'
    path.write_text(json.dumps({'deployment_status': 'not_deployed'}))
    assert load_target(path)['deployment_status'] == 'not_deployed'
    for target in [
        {},
        {'deployment_status': 'deployed'},
        {'deployment_status': 'not_deployed', 'site_url': 'https://example.org'},
        {'deployment_status': 'deployed', 'site_url': 'https://user:secret@example.org',
         'health_url': 'https://example.org/_stcore/health', 'chart_views': ['Overview']},
    ]:
        path.write_text(json.dumps(target))
        with pytest.raises(ValueError):
            load_target(path)


def test_health_rejects_error_pages_and_request_failures():
    target = {'site_url': 'https://example.org', 'health_url': 'https://example.org/_stcore/health'}
    def get(url, **kwargs):
        return SimpleNamespace(status_code=200, text='<html>Login</html>' if 'health' in url else '')
    checks = check_http(target, get)
    assert checks[0]['passed']
    assert not checks[1]['passed']
    assert all(c['passed'] for c in check_http(target, lambda *a, **k: SimpleNamespace(status_code=200, text='ok')))
    def failed(*args, **kwargs):
        raise requests.ConnectionError('secret URL must not leak')
    checks = check_http(target, failed)
    assert not any(c['passed'] for c in checks)
    assert 'secret' not in json.dumps(checks)


@pytest.mark.parametrize('status', ['stale', 'missing', 'invalid', 'insufficient history'])
def test_live_audit_fails_unhealthy_observations(status):
    row = {'series_id': 'TEST', 'observation': {'status': status}, 'provenance': 'FRED API'}
    assert audit_failures([row], ['TEST'])


def test_live_audit_requires_complete_unique_error_free_api_coverage():
    row = {'series_id': 'TEST', 'observation': {'status': 'fresh'}, 'provenance': 'FRED API'}
    assert not audit_failures([row], ['TEST'])
    assert audit_failures([], ['TEST'])
    assert audit_failures([row, row], ['TEST'])
    assert audit_failures([row], ['TEST', 'OTHER'])
    for change in [{'metadata_error': 'failed'}, {'error': 'failed'}, {'provenance': 'S3 archive'}]:
        assert audit_failures([dict(row, **change)], ['TEST'])


def test_missing_credentials_fail_before_any_network_request(tmp_path, monkeypatch):
    output = tmp_path / 'audit.json'
    monkeypatch.setattr('config.FRED_API_KEY', '')
    monkeypatch.setattr('config.EIA_API_KEY', '')
    monkeypatch.setattr('sys.argv', ['audit', '--strict', '--output', str(output)])
    with patch('scripts.audit_live_sources.requests.get') as get:
        assert audit_main() == 1
        get.assert_not_called()
    assert json.loads(output.read_text())['status'] == 'failed'


def test_not_deployed_is_distinct_from_pass(tmp_path, monkeypatch):
    config = tmp_path / 'target.json'
    output = tmp_path / 'report.json'
    config.write_text('{"deployment_status": "not_deployed"}')
    monkeypatch.setattr('sys.argv', ['monitor', '--config', str(config), '--output', str(output)])
    assert deployment_main() == 2
    assert json.loads(output.read_text())['status'] == 'not_deployed'


def test_http_success_cannot_hide_browser_failure(tmp_path, monkeypatch):
    config = tmp_path / 'target.json'
    output = tmp_path / 'report.json'
    config.write_text(json.dumps({'deployment_status': 'deployed', 'site_url': 'https://example.org',
        'health_url': 'https://example.org/_stcore/health', 'chart_views': ['Overview']}))
    monkeypatch.setattr('sys.argv', ['monitor', '--config', str(config), '--output', str(output)])
    with patch('scripts.check_deployment.check_http', return_value=[{'check': 'http', 'passed': True}]), \
         patch('scripts.check_deployment.check_charts', return_value=[{'check': 'browser', 'passed': False}]):
        assert deployment_main() == 1
    assert json.loads(output.read_text())['status'] == 'failed'
