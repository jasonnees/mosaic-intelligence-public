"""Authenticated opt-in source audit; emits no keys or request exception text."""
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
import config
from risk_catalog import INDICATORS
from risk_data import RiskDataService, assess

def audit_failures(rows, expected_ids):
    """Fail closed on incomplete coverage, unhealthy observations or source errors."""
    failures = []
    ids = [row.get('series_id') for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(expected_ids):
        failures.append('Catalog coverage mismatch')
    for row in rows:
        if (row.get('metadata_error') or row.get('error')
                or row.get('observation', {}).get('status') != 'fresh'
                or row.get('provenance') not in {'FRED API', 'EIA API'}):
            failures.append(f"{row.get('series_id')}: source error or observation not fresh")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true', help='Exit nonzero for missing keys or unhealthy sources')
    parser.add_argument('--output', help='Save timestamped JSON evidence to this path')
    args = parser.parse_args()
    missing = [name for name in ('FRED_API_KEY', 'EIA_API_KEY') if not getattr(config, name)]
    if args.strict and missing:
        report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed',
                  'failures': ['Missing credentials: ' + ', '.join(missing)], 'series': []}
        if args.output:
            Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 1
    service = RiskDataService()
    rows = []
    for indicator in INDICATORS:
        row = {'series_id': indicator.series_id, 'url': indicator.source_url}
        if indicator.source == 'fred':
            try:
                response = requests.get('https://api.stlouisfed.org/fred/series',
                    params={'series_id': indicator.series_id, 'api_key': config.FRED_API_KEY, 'file_type':'json'},timeout=30)
                response.raise_for_status()
                metadata = response.json()['seriess'][0]
                row['metadata'] = {k:metadata[k] for k in ['title','frequency','units','seasonal_adjustment','observation_end','last_updated']}
            except Exception:
                row['metadata_error'] = 'Metadata request failed'
        fetched = service.fetch(indicator,730)
        row['observation'] = asdict(assess(fetched.frame,indicator))
        row['provenance'] = fetched.provenance
        row['error'] = fetched.error
        rows.append(row)
        time.sleep(1.2)
    failures = audit_failures(rows, [indicator.series_id for indicator in INDICATORS])
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Authenticated API metadata and observations; point-in-time availability only',
              'status': 'failed' if failures else 'passed', 'failures': failures, 'series': rows}
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 1 if args.strict and failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
