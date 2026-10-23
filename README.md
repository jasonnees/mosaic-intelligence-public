# Market Risk Explorer

A household-focused Streamlit dashboard with **77 unique indicators** from free public feeds: 76 FRED series and one directly from EIA. This public deployment copy starts with clean history; the original development repository remains private.

Explore equity risk, recession and growth, inflation, interest rates, credit stress and housing. A separate portfolio implications view offers planning questions tied to these domains. Overview → domain → indicator charts, selectable history, observation filters and CSV downloads are supported. Select any indicator row to show its chart below the table. This works in the overview, every risk domain and the full Data catalog; the catalog fetches only the selected series.

## What changed

The active catalog replaces the 239-row framework with 77 distinct, explicitly defined indicators. Unmapped indicators, duplicate feeds, the discontinued TED spread and specialized or ambiguous sources are demoted. Every legacy row has a disposition in [the migration ledger](docs/indicator-migration.csv). `indicators_300.py` remains only for compatibility with historical scripts; the dashboard never imports it.

Names now describe what the source actually measures: corporate option-adjusted spreads rather than CDX, all-loan delinquency rather than auto delinquency, and the actual four-week claims average (`IC4WSA`). Units remain explicit; Treasury spreads are percentage points, not mislabeled basis points. Price indexes, income and selected activity series use calendar-year growth with a required prior-year comparison.

There are no preset bullish/bearish fallbacks, allocation recommendations or opaque composite score. Six explicit watch rules identify conditions worth examining; most indicators provide context. Stale, missing, future-dated and insufficient-history observations cannot trigger or clear a watch condition. Counts are never presented as a calibrated probability or portfolio score.

## Setup

Requires Python 3.11 or later.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set FRED_API_KEY and EIA_API_KEY in .env
streamlit run app.py
```

Obtain free keys from [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) and [EIA](https://www.eia.gov/opendata/register.php). FRED serves the energy price series as well as macro and market data; the EIA key enables US residential electricity prices. Missing keys leave affected observations unavailable and show setup guidance. Keys are never included in user-facing request errors.

**AWS is optional.** The default `DATA_SOURCE_MODE=api` needs no AWS package, bucket or credentials. Streamlit caches observations for an hour; Refresh clears that cache. Only the overview basket or selected domain is fetched, rather than every catalog entry on every page load.

For an existing S3 archive:

```sh
pip install -r requirements-aws.txt
# Set DATA_SOURCE_MODE=s3, AWS_REGION, S3_BUCKET_NAME and normal AWS credentials
```

In the Explorer, S3 supplements history and public APIs refresh observations. API values win overlapping dates, including revisions. If an API fails, archived observations remain visible with their actual observation age and archive provenance. No new AWS infrastructure is provisioned. The optional legacy `HybridDataManager` retains its S3-first contract for existing scripts. Data Exchange is disabled by default.

## Reliability

Each displayed observation includes date, age, frequency, freshness budget, source class, retrieval timestamp, actual transport provenance and transformation. The Data catalog links directly to source notes and can be downloaded without API access.

Freshness means observation age is within an operational budget: daily 10 days, weekly 21, monthly 100 and quarterly 210. Budgets allow for weekends, reference-period dating and release lags; they do not implement official release calendars. They can miss a delayed monthly release within the budget. A fresh series can still be revised, and is not necessarily real-time. The source date is the observation period, not the publication date.

FRED carries both official public-agency data and third-party series. Third-party market indexes, mortgage surveys and credit spreads are identified explicitly; free access does not imply unrestricted redistribution. Index histories may be shorter than the selected chart window; equity price growth excludes dividends. No synthetic history is inserted.

## Validation

```sh
pip install -r requirements-dev.txt
python -m pytest -q
# Optional public page audit (no key):
python scripts/audit_sources.py > docs/source-audit.json
# Optional authenticated metadata and observation audit:
python scripts/audit_live_sources.py > docs/live-source-audit.json
# Regenerate the legacy disposition ledger:
python scripts/build_migration.py
```

Offline tests cover source routing, zero values, duplicates, revised snapshots, calendar-year comparisons, missing bases, freshness boundaries, future dates, archive fallback and Streamlit navigation. GitHub Actions runs without credentials and without boto3. Live audit files are point-in-time evidence, not a promise of continued source availability. See [migration details and limitations](docs/MIGRATION.md).

## Deployment and monitoring

See [deployment instructions](docs/DEPLOYMENT.md) for Streamlit Community Cloud setup, secret configuration, and daily authenticated feed, availability and populated-chart checks. `monitoring.json` explicitly records whether an app is deployed. Offline tests and historical audit snapshots do not establish current production health.

## Architecture

| File | Responsibility |
|---|---|
| `app.py` | Household risk views, charts, filters and exports |
| `risk_catalog.py` | Curated definitions, units, frequency, budgets and watch rules |
| `risk_data.py` | Source routing, archive merge, transformations and assessment |
| `data_fetcher.py` | Existing FRED, EIA, BLS and Treasury clients |
| `s3_reader.py` | Optional historical archive and legacy data manager |
| `api.py` | Preserved optional FastAPI custom-indicator ingestion |
| `config.py` | Keys, optional archive settings and legacy integration metadata |
| `indicators_300.py` | Inactive legacy framework for historical script compatibility |

The infrastructure, backfill and target-range scripts are retained for existing users. They are not part of the active Explorer and their legacy indicator lists are not the curated catalog. The custom ingestion API remains separate from the curated dashboard.

Educational information only; not individualized investment advice.
