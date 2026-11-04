import json
from unittest.mock import patch

import requests

from scripts.probe_frontend_assets import asset_paths, fetch, probe

APP = 'https://example.org/~/+/'
LOCAL = 'http://127.0.0.1:8511/'
HTML = b'<script src="./static/js/main.js"></script>'
GOOD = {'status': 200, 'sha256': 'same'}


def test_manifest_uses_same_origin_frontend_files_without_query_strings():
    html = '''<script src="./static/js/main.js?api_key=secret"></script>
      <link rel="stylesheet" href="./static/css/app.css">
      <script src="https://other.org/static/js/other.js"></script>
      <link href="./static/media/font.woff2">'''
    assert asset_paths(html, APP) == ['static/css/app.css', 'static/js/main.js']


def test_an_html_shell_without_frontend_files_cannot_pass():
    with patch('scripts.probe_frontend_assets.fetch', return_value=(GOOD, b'<html>Login</html>')):
        report = probe(APP, LOCAL)
    assert report['status'] == 'failed'
    assert report['summary']['assets'] == 0


def test_recovered_asset_timeout_remains_visible_and_fails_clean_delivery_gate():
    attempts = []
    def get(url, timeout):
        if url == APP:
            return GOOD, HTML
        if url.startswith(LOCAL):
            return GOOD, b'js'
        attempts.append(url)
        return ({'error': 'ReadTimeout'}, b'') if len(attempts) == 1 else (GOOD, b'js')
    with patch('scripts.probe_frontend_assets.fetch', side_effect=get):
        report = probe(APP, LOCAL)
    assert report['status'] == 'failed'
    assert report['summary'] == {'assets': 1, 'identical': 1, 'retried': 1, 'remote_failures': 0}


def test_equal_assets_pass_but_different_content_fails():
    def get(url, timeout):
        return GOOD, HTML if url == APP else b'js'
    with patch('scripts.probe_frontend_assets.fetch', side_effect=get):
        assert probe(APP, LOCAL)['status'] == 'passed'
    def different(url, timeout):
        return ({'status': 200, 'sha256': 'different'} if url.startswith(LOCAL) else GOOD,
                HTML if url == APP else b'js')
    with patch('scripts.probe_frontend_assets.fetch', side_effect=different):
        assert probe(APP, LOCAL)['status'] == 'failed'


def test_request_exception_text_cannot_leak_into_diagnostics():
    with patch('scripts.probe_frontend_assets.requests.get', side_effect=requests.ConnectionError('api_key=secret')):
        result, body = fetch(APP)
    assert result['error'] == 'ConnectionError' and body == b''
    assert 'secret' not in json.dumps(result)
