"""Reproducible disposition ledger for every legacy indicator row."""
import csv
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indicators_300 import CAT, SRC
from risk_catalog import BY_ID

if __name__ == '__main__':
    seen = set()
    rows = []
    for category, data in CAT.items():
        for legacy in data['d']:
            name = legacy[0]
            source = SRC.get(name, [])
            sid = source[0] if source else ''
            replacement = 'IC4WSA' if name == 'Initial Claims (4-wk)' else sid
            if replacement in BY_ID:
                action = 'consolidated duplicate' if replacement in seen else 'retained / corrected definition'
                reason = 'Use the canonical name, units and transformation in risk_catalog.py; no preset signals.'
                seen.add(replacement)
            else:
                action = 'demoted to legacy'
                if not sid:
                    reason = 'No integrated public source mapping; unavailable in the working application.'
                elif sid == 'TEDRATE':
                    reason = 'FRED discontinued this series in 2022.'
                elif sid in {'MICH','UMCSENT'}:
                    reason = 'Source publication embargo; core set favors directly observed household conditions.'
                elif sid.startswith(('PET.','NG.')):
                    reason = 'Specialized energy supply detail; use household energy prices in core. Some legacy routes lack unique facets.'
                else:
                    reason = 'Lower household relevance, overlapping context or mapping needing further validation.'
                replacement = ''
            rows.append({'legacy_category':category,'legacy_name':name,'legacy_series':sid,'disposition':action,'core_series':replacement,'reason':reason})
    with open('docs/indicator-migration.csv','w',newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
