# Market Risk Explorer

A household-focused Streamlit dashboard with **77 unique indicators** from free public feeds: 76 FRED series and one directly from EIA. This public deployment copy starts with clean history; the original development repository remains private.

Explore equity risk, recession and growth, inflation, interest rates, credit stress and housing. A separate portfolio implications view offers planning questions tied to these domains. Overview → domain → indicator charts, selectable history, observation filters and CSV downloads are supported. Select any indicator row to show its chart below the table. This works in the overview, every risk domain and the full Data catalog; the catalog fetches only the selected series.

## What changed

The active catalog replaces the 239-row framework with 77 distinct, explicitly defined indicators. Unmapped indicators, duplicate feeds, the discontinued TED spread and specialized or ambiguous sources are demoted. Every legacy row has a disposition in [the migration ledger](docs/indicator-migration.csv). `indicators_300.py` remains only for compatibility with historical scripts; the dashboard never imports it.

Names now describe what the source actually measures: corporate option-adjusted spreads rather than CDX, all-loan delinquency rather than auto delinquency, and the actual four-week claims average (`IC4WSA`). Units remain explicit; Treasury spreads are percentage points, not mislabeled basis points. Price indexes, income and selected activity series use calendar-year growth with a required prior-year comparison.

There are no preset bullish/bearish fallbacks, allocation recommendations or opaque composite score. Seven explicit watch rules identify conditions worth examining; most indicators provide context. Stale, missing, future-dated and insufficient-history observations cannot trigger or clear a watch condition. Counts are never presented as a calibrated probability or portfolio score.

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

## Mosaic Income theme and indicator guidance

The app uses the original [Mosaic Income](https://mosaicincome.substack.com/) wordmark, a dark navy background and domain-specific cyan, violet, amber, blue, rose and mint chart colors. The wordmark is unchanged; display brightness is adjusted with CSS for contrast. Its source is recorded in `assets/README.md`.

Every one of the 77 indicators has a rising interpretation, a falling interpretation and a series-specific caution. Direction compares the displayed value with about three months earlier (one year for quarterly series); year-over-year series compare growth rates, not price levels. Actual comparison dates and changes are shown. Missing or stale observations, future dates and missing prior-year bases cannot support direction. Gappy comparison history produces “No comparison.”

Seven explicit watch rules remain separate from direction and data-quality warnings. Headline PCE inflation above 2% is a comparison with the Fed's longer-run benchmark, not a forecast of policy action. Core PCE and CPI are not assigned that policy benchmark. VIX 30 is an operational app threshold, not an official crisis boundary. Every rule links to its source and limitation. An untriggered rule is not an all-clear. No thresholds were invented for the other indicators; each displays descriptive context and its own limitations.

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

### CPI and GDP component pages

Choose **CPI & components** or **GDP & components** in the sidebar. The existing
FRED key loads CPI and official BEA GDP contributions. An optional free
`BEA_API_KEY` in Streamlit's secrets (top-level TOML string) loads the entire
GDP table directly; FRED remains the fallback if BEA is unavailable. Do not commit keys.
Direct links can use `?view=CPI%20%26%20components` or
`?view=GDP%20%26%20components`.

Both pages include a dark stacked contribution chart, white headline line,
component heatmaps, history controls and CSV exports. GDP uses published real,
annualized quarterly contributions, not changes in chained-dollar component
levels. Nested table rows must not be added together. The cyclical section
compares durable consumption, residential investment and business equipment,
with a link to Eric Basmajian's public EPB framework; it does not reproduce an
EPB index.

CPI uses BLS unadjusted indexes delivered by FRED. Its contribution bars are
**Mosaic estimates**, using price-updated, dated December BLS CPI-U relative
importance shares. Intervals crossing an annual basket pivot are calculated
in separate segments and expressed against the same headline-index base.
Rounded basket shares/indexes and reweighting can cause a difference from
headline inflation; that difference is displayed, never normalized away.
The current verified baskets cover December 2024 and December 2025; monthly
effects cover 2025–2026 and 12-month effects start December 2025. Weights expire
after a year. Add a sourced annual basket to `CPI_WEIGHTS` to extend coverage.
Index/rate history uses each series' full available FRED history, independently
of weight coverage. No filling of missing comparison endpoints or weight pivots.
Monthly NSA changes contain seasonality; they are not annualized. CPI does not
inherit the Federal Reserve's 2% PCE target.

### Market History

**Market history** opens twelve historical stress cases: 1929–32, 1973–74,
1980–82, 1987, 1998, 2000–02, 2007–09, 2011, 2018, 2020, 2022 and the 2023
banking stress. Each button selects fixed before/during/after windows, sourced
context, specific stress mechanisms, relevant macro charts and blind spots.
These windows override the general sidebar History selector. Deep links support
`?view=Market%20history&regime=gfc` (IDs are in `market_history_catalog.py`).

This page is independent of API keys: `data/market_history/` holds a bounded,
compressed teaching snapshot through December 2024, with source metadata and
SHA-256 checksums. It includes twenty public-agency macro series, Kenneth
French's broad U.S. daily total returns, and 108 selected FRED/ALFRED archive
checks from the prior research. It does not publish the private research folder,
third-party FRED equity/credit histories, or credentials. Missing period data and
archive gaps remain explicit.

The equity benchmark is the French market factor plus the risk-free return,
compounded daily and rebased at the first displayed close. Drawdowns are relative
to the running high within that displayed window. They are not S&P 500 price
returns, and there is no splicing with Shiller, Nasdaq or Dow history. Pink
shading denotes the selected study interval, not recession dates.

Macro charts and comparison tables contain revised reference-period history;
only the separate archived section uses as-of vintages. **Show pre-stress
reference periods only** withholds reference periods ending on or after stress
starts, including incomplete months/quarters. It does not remove revision
hindsight or simulate release lags. The before/during table uses the last valid,
completed pre-stress reference period with bounded staleness; it never labels a
missing value as zero. Period downloads contain the exact visible market and
indicator rows, comparison readings, archive checks and source/calculation scope.

To rebuild from the original saved public-source research, run
`python scripts/build_market_history.py --research-dir PATH`. The builder checks
raw source hashes against that research manifest, copies only the explicit
series allowlist and fetches long CPI history via a server-side FRED key when
needed. Source retrieval arguments, units, transformations and snapshot bounds
are retained in `manifest.json`. Updating this static study is a deliberate
source/data revision; the ordinary refresh button does not replace historical
snapshots with current feed data.

On the CPI page the sidebar **History** selector defaults to **All available**
and supports 1, 2, 5, 10 and 20 years. This one selector controls the component
chart, table, source coverage and CSV download, plus the available contribution
estimates. Chart buttons and a draggable timeline allow closer inspection. Each component retains its own source start and gaps. The component
table defaults to the complete selected history, with an optional latest-12-period
view. The coverage expander reports each component's first and latest usable
inflation observation, and CSV exports use the selected history range. Historical
basket-weight limits apply only to contribution estimates, not these rate charts.
