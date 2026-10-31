"""Check the configured Streamlit deployment; never infer or invent a URL."""
import argparse
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
import requests


def load_target(path):
    target = json.loads(Path(path).read_text())
    status = target.get('deployment_status')
    if status not in {'not_deployed', 'deployed'}:
        raise ValueError('deployment_status must be not_deployed or deployed')
    if status == 'not_deployed':
        if target.get('site_url') or target.get('health_url'):
            raise ValueError('Set deployment_status to deployed when supplying URLs')
        return target
    for key in ('site_url', 'health_url'):
        url = urlsplit(target.get(key) or '')
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError(f'{key} must be an HTTPS URL without credentials, query or fragment')
    views = target.get('chart_views')
    if not isinstance(views, list) or not views or not all(isinstance(view, str) and view for view in views):
        raise ValueError('Configure at least one chart view')
    return target


def check_http(target, get=requests.get):
    checks = []
    for key in ('site_url', 'health_url'):
        try:
            response = get(target[key], timeout=60)
            passed = response.status_code == 200
            if key == 'health_url':
                passed = passed and response.text.strip().lower() == 'ok'
            checks.append({'check': key, 'passed': passed, 'status_code': response.status_code})
        except requests.RequestException:
            checks.append({'check': key, 'passed': False, 'error': 'Request failed'})
    return checks


def check_charts(target, timeout_ms=180000):
    from playwright.sync_api import sync_playwright, expect
    checks = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.set_default_timeout(timeout_ms)
        current_view = 'startup'
        try:
            page.goto(target['site_url'], wait_until='domcontentloaded')
            # Community Cloud wraps the actual app in a named iframe. A direct
            # Streamlit server has no wrapper; wait for either surface to exist.
            page.wait_for_function("""() => document.querySelector('iframe[title="streamlitApp"]')
                || [...document.querySelectorAll('h1')].some(h => h.textContent.trim() === 'Boldin Market Risk Explorer')""")
            app = (page.frame_locator('iframe[title="streamlitApp"]')
                   if page.locator('iframe[title="streamlitApp"]').count() else page)
            app.get_by_role('heading', name='Boldin Market Risk Explorer', exact=True).wait_for()
            for view in target['chart_views']:
                current_view = view
                app.get_by_test_id('stSidebar').get_by_text(view, exact=True).click()
                app.get_by_role('heading', name=view if view != 'Overview' else 'Household risk overview', exact=True).wait_for()
                # Wait for the new run, not a stale chart left by the prior view.
                expect(app.get_by_test_id('stApp')).to_have_attribute(
                    'data-test-script-state', 'notRunning', timeout=timeout_ms)
                expect(app.locator('[data-testid="stElementContainer"][data-stale="true"]')).to_have_count(0, timeout=timeout_ms)
                if app.locator('[data-testid="stException"]').count():
                    raise RuntimeError('Application exception')
                # An actual SVG data path is required, not an empty plot container.
                expect(app.locator('[data-testid="stPlotlyChart"] .js-line').first).to_have_attribute(
                    'd', re.compile(r'.{11,}'), timeout=timeout_ms)
                checks.append({'check': f'chart:{view}', 'passed': True})
        except Exception:
            # Browser exceptions can contain URLs; keep diagnostics credential free.
            checks.append({'check': 'browser', 'passed': False, 'view': current_view, 'error': 'App title, navigation, completed run or populated chart check failed'})
        finally:
            browser.close()
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='monitoring.json')
    parser.add_argument('--output', default='deployment-report.json')
    parser.add_argument('--http-only', action='store_true', help='Diagnostic only; does not verify charts')
    args = parser.parse_args()
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed', 'checks': []}
    code = 1
    try:
        target = load_target(args.config)
        if target['deployment_status'] == 'not_deployed':
            report['status'] = 'not_deployed'
            code = 2
        else:
            report['checks'] = check_http(target)
            if all(check['passed'] for check in report['checks']) and not args.http_only:
                report['checks'] += check_charts(target)
            if report['checks'] and all(check['passed'] for check in report['checks']):
                report['status'] = 'http_only' if args.http_only else 'passed'
                code = 0
    except Exception:
        report['checks'].append({'check': 'configuration_or_runner', 'passed': False,
                                 'error': 'Invalid configuration or monitoring runner failure'})
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
