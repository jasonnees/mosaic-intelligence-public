"""Read official FRED pages to check catalog identities; no credentials needed.

Run: python scripts/audit_sources.py > docs/source-audit.json
This verifies public metadata, not authenticated API behavior or future availability.
"""
import concurrent.futures
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from risk_catalog import INDICATORS


def check(indicator):
    result = {'series_id': indicator.series_id, 'url': indicator.source_url}
    try:
        response = requests.get(indicator.source_url, timeout=30)
        result['http_status'] = response.status_code
        title = re.search(r'<title>(.*?)</title>', response.text, re.S)
        result['title'] = html.unescape(title.group(1).strip()) if title else ''
        result['discontinued'] = 'DISCONTINUED' in result['title'].upper()
        result['status'] = 'verified page' if response.ok and indicator.series_id in result['title'] and not result['discontinued'] else 'needs review'
        if indicator.source == 'eia':
            result['status'] = 'official browser only; API needs key'
    except requests.RequestException:
        result['status'] = 'unreachable'
    return result

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(check, INDICATORS))
    print(json.dumps({'checked_at': datetime.now(timezone.utc).isoformat(), 'scope': 'Public source page identity, not API observations', 'series': rows}, indent=2))
