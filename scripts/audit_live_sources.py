"""Authenticated opt-in source audit; emits no keys or request exception text."""
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from data_fetcher import FREDClient, source_error
from risk_catalog import INDICATORS
from risk_data import RiskDataService, assess_result, result_freshness_context

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
    fred = FREDClient() if config.FRED_API_KEY else None
    service = RiskDataService(fred=fred)
    rows = []
    for indicator in INDICATORS:
        row = {'series_id': indicator.series_id, 'url': indicator.source_url}
        if indicator.source == 'fred':
            try:
                row['metadata'] = fred.get_metadata(indicator.series_id)
            except Exception as error:
                row['metadata_error'] = source_error('fred', error)
        fetched = service.fetch(indicator,730)
        row['observation'] = asdict(assess_result(fetched,indicator))
        row['freshness_rule'] = result_freshness_context(fetched, indicator, row['observation']['observed_at'])
        row['provenance'] = fetched.provenance
        row['error'] = fetched.error
        rows.append(row)
    failures = audit_failures(rows, [indicator.series_id for indicator in INDICATORS])
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Authenticated API metadata and observations; point-in-time availability only',
              'fred_requests': fred.request_diagnostics if fred is not None else {},
              'status': 'failed' if failures else 'passed', 'failures': failures, 'series': rows}
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 1 if args.strict and failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
