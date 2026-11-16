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


def classify_row(row):
    """Operational health is independent of whether a growth rate is calculable."""
    observation = row.get('observation', {})
    feed_ok = (not row.get('error') and row.get('live_ok', True)
               and row.get('provenance') in {'FRED API', 'EIA API'})
    limitation = (observation.get('known_limitation') == 'bls_cpi_october_2025_missing_base'
                  and row.get('series_id') in {'CPIAUCSL', 'CPILFESL', 'CUSR0000SEHA'}
                  and observation.get('observed_at') == '2026-10-01'
                  and observation.get('status') == 'insufficient history')
    reasons = []
    if not feed_ok:
        reasons.append('feed_unavailable')
    if row.get('metadata_error'):
        reasons.append('metadata_error')
    status = observation.get('status', 'missing')
    if status != 'fresh' and not limitation:
        reasons.append('observation_' + status.replace(' ', '_'))
    return {'feed_status': 'available' if feed_ok else 'failed',
            'observation_status': status,
            'known_limitation': ({'code': observation['known_limitation'],
                'source_url': 'https://www.bls.gov/cpi/notices/2026/12m-changes-202610.htm'}
                if limitation else None),
            'actionable_reasons': reasons}


def audit_failures(rows, expected_ids):
    """Fail closed except for an explicitly identified, date-bounded source gap."""
    failures = []
    ids = [row.get('series_id') for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(expected_ids):
        failures.append('Catalog coverage mismatch')
    for row in rows:
        reasons = classify_row(row)['actionable_reasons']
        if reasons:
            failures.append(f"{row.get('series_id')}: {', '.join(reasons)}")
    return failures


def write_report(report, output=None, summary=None):
    payload = json.dumps(report, indent=2) + '\n'
    if output:
        Path(output).write_text(payload)
    if summary:
        lines = ['## Source monitoring: ' + report['status'], '',
                 'This result checks data sources; deployment availability is checked separately.', '',
                 f"Mode: {report.get('mode', 'credentials check')}", '',
                 f"Actionable failures: {len(report['failures'])}",
                 f"Warnings: {len(report.get('warnings', []))}", '',
                 '| Series | Feed | Observation | Actionable reasons | Known limitation |',
                 '|---|---|---|---|---|']
        for row in report['series']:
            limitation = row['known_limitation']
            lines.append(f"| {row['series_id']} | {row['feed_status']} | {row['observation_status']} | "
                         f"{', '.join(row['actionable_reasons']) or 'None'} | "
                         f"{limitation['code'] if limitation else 'None'} |")
        lines += ['', *['- ' + failure for failure in report['failures']],
                  *['- ' + warning for warning in report.get('warnings', [])]]
        Path(summary).write_text('\n'.join(lines) + '\n')
    print(payload, end='')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true', help='Exit nonzero for missing keys or unhealthy sources')
    parser.add_argument('--output', help='Save timestamped JSON evidence to this path')
    parser.add_argument('--summary', help='Write a Markdown job summary')
    parser.add_argument('--observations-only', action='store_true', help='Skip weekly FRED metadata checks')
    args = parser.parse_args()
    missing = [name for name in ('FRED_API_KEY', 'EIA_API_KEY') if not getattr(config, name)]
    if args.strict and missing:
        report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed',
                  'failures': ['Missing credentials: ' + ', '.join(missing)], 'series': []}
        write_report(report, args.output, args.summary)
        return 1
    fred = FREDClient() if config.FRED_API_KEY else None
    service = RiskDataService(fred=fred)
    rows = []
    for indicator in INDICATORS:
        row = {'series_id': indicator.series_id, 'url': indicator.source_url}
        row['metadata_status'] = 'not_checked' if indicator.source == 'fred' else 'not_applicable'
        if indicator.source == 'fred' and not args.observations_only:
            try:
                row['metadata'] = fred.get_metadata(indicator.series_id)
                if not row['metadata']['frequency'].lower().startswith(indicator.frequency):
                    row['metadata_error'] = 'FRED frequency differs from catalog'
                row['metadata_status'] = 'failed' if row.get('metadata_error') else 'available'
            except Exception as error:
                row['metadata_error'] = source_error('fred', error)
                row['metadata_status'] = 'failed'
        fetched = service.fetch(indicator,730)
        row['observation'] = asdict(assess_result(fetched,indicator))
        row['freshness_rule'] = result_freshness_context(fetched, indicator, row['observation']['observed_at'])
        row['provenance'] = fetched.provenance
        row['error'] = fetched.error
        row['live_ok'] = fetched.live_ok
        row['warnings'] = list(fetched.warnings)
        row.update(classify_row(row))
        rows.append(row)
    failures = audit_failures(rows, [indicator.series_id for indicator in INDICATORS])
    warnings = [f"{row['series_id']}: {warning}" for row in rows for warning in row['warnings']]
    warnings += [f"{row['series_id']}: documented comparison gap; value remains unavailable"
                 for row in rows if row['known_limitation']]
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Authenticated API observations; point-in-time availability only',
              'mode': 'observations' if args.observations_only else 'metadata_and_observations',
              'fred_requests': fred.request_diagnostics if fred is not None else {},
              'status': 'failed' if failures else ('passed_with_warnings' if warnings else 'passed'),
              'failures': failures, 'warnings': warnings, 'series': rows}
    write_report(report, args.output, args.summary)
    return 1 if args.strict and failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
