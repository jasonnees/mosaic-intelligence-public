"""Compare public Streamlit startup assets with a local server, without API keys."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from urllib.parse import urljoin, urlsplit

import requests


def fetch(url, timeout=12):
    started = time.monotonic()
    try:
        response = requests.get(url, timeout=(5, timeout))
        body = response.content
        result = {'status': response.status_code,
                  'content_type': response.headers.get('content-type', '').split(';')[0],
                  'bytes': len(body), 'sha256': sha256(body).hexdigest()}
    except requests.RequestException as error:
        result, body = {'error': type(error).__name__}, b''
    result['seconds'] = round(time.monotonic() - started, 3)
    return result, body


def asset_paths(html, app_url):
    paths = set()
    origin = urlsplit(app_url)

    class Parser(HTMLParser):
        def handle_starttag(self, tag, attributes):
            attributes = dict(attributes)
            value = attributes.get('src') if tag == 'script' else attributes.get('href') if tag == 'link' else None
            if not value:
                return
            parsed = urlsplit(urljoin(app_url, value))
            if ((parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc)
                    and '/static/' in parsed.path and parsed.path.endswith(('.js', '.css'))):
                paths.add('static/' + parsed.path.split('/static/', 1)[1])

    Parser().feed(html)
    return sorted(paths)


def probe(app_url, local_url, timeout=12, workers=6):
    html_attempts = []
    body = b''
    for _ in range(2):
        result, body = fetch(app_url, timeout)
        html_attempts.append(result)
        if result.get('status') == 200 and body:
            break
    paths = asset_paths(body.decode('utf-8', errors='replace'), app_url)

    def compare(path):
        local, _ = fetch(urljoin(local_url, path), timeout)
        remote_attempts = []
        for _ in range(2):
            remote, _ = fetch(urljoin(app_url, path), timeout)
            remote_attempts.append(remote)
            if remote.get('status') == 200:
                break
        remote = remote_attempts[-1]
        identical = (local.get('status') == remote.get('status') == 200
                     and local['sha256'] == remote['sha256'])
        return {'asset': path, 'local': local, 'remote_attempts': remote_attempts,
                'identical': identical}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(compare, paths))
    summary = {'assets': len(rows), 'identical': sum(row['identical'] for row in rows),
               'retried': sum(len(row['remote_attempts']) > 1 for row in rows),
               'remote_failures': sum(row['remote_attempts'][-1].get('status') != 200 for row in rows)}
    passed = bool(rows) and all(row['identical'] and len(row['remote_attempts']) == 1 for row in rows) and len(html_attempts) == 1
    return {'status': 'passed' if passed else 'failed', 'timeout_seconds': timeout,
            'workers': workers, 'html_attempts': html_attempts, 'summary': summary, 'assets': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-url', required=True, help='Observed public app-frame URL, ending with /')
    parser.add_argument('--local-url', default='http://127.0.0.1:8511/')
    parser.add_argument('--output', default='frontend-assets.json')
    args = parser.parse_args()
    report = probe(args.app_url, args.local_url)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], **report['summary']}))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
