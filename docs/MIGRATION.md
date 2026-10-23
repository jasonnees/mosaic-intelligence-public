# Migration to the household risk catalog

The legacy framework contains 239 indicator rows, many without working source mappings. The Explorer uses 77 distinct series, with no duplicate weighting. The full row-level keep/consolidate/demote ledger is `indicator-migration.csv`.

Selection favors identifiable public feeds, household relevance, modest maintenance and honest definitions. Equity has a small selection because this project has no dependable free implementation for market breadth, order flow, dark pools or proprietary derivatives. Those gaps are not filled with static signals. Inflation includes energy prices rather than specialized inventory and export routes. Portfolio implications is a planning view, not an additional batch of indicators.

Corrections include:

- `ICSA` replaced by `IC4WSA` for the four-week claims average.
- `BAMLC0A0CM` and `BAMLH0A0HYM2` labeled corporate option-adjusted spreads, not CDX indexes; duplicates consolidated.
- `DRALACBS` labeled all-loan delinquency; `DRSFRMACBS` no longer labeled specifically 90+ days.
- `MICH` demoted rather than presented as generic consumer expectations. Its source is an inflation expectation survey with delayed public availability.
- `TEDRATE` removed from the core because FRED marks it discontinued.
- Repeated curve, lending standards, mortgage delinquency and high-yield source mappings consolidated.
- Core PCE prices, continued claims, household debt service, additional Treasury maturities, 15-year mortgage rates, retail gasoline and residential electricity improve household coverage.

Primary references: [TED discontinuation](https://fred.stlouisfed.org/series/TEDRATE), [four-week claims](https://fred.stlouisfed.org/series/IC4WSA), [all-loan delinquency](https://fred.stlouisfed.org/series/DRALACBS), [Michigan inflation expectations](https://fred.stlouisfed.org/series/MICH). Each catalog entry links to its own source.

## Behavior and compatibility

The existing `streamlit run app.py` command is unchanged. The app retains domain drilldown, indicator charts and adjustable history; filters now distinguish unavailable data explicitly. Source and reliability exports are new. The former composite and bullish/bearish target-range classifications are intentionally retired because their preset and mixed-unit inputs did not justify a household risk score.

Existing BLS, Treasury and custom ingestion code remains available. Legacy imports continue to work, but the old scoring helpers and target-range scripts should not be used to generate Explorer conclusions. Optional infrastructure scripts retain the existing AWS resource names. No bucket was renamed, infrastructure deployed or paid service added.

The current GitHub baseline did not contain the 22 tests described in the referenced conversation. This branch adds a reproducible offline suite and CI. Snapshot chronology, duplicate revision handling, zero-value preservation and calendar-year lookbacks are covered by regression tests.

## Remaining limits

- Freshness uses observation-age budgets, not provider release calendars, publication timestamps or per-series SLAs. Late releases inside a budget may go undetected.
- No calibrated risk model or validated asset-allocation model is claimed. Watch thresholds are transparent heuristics and there is no aggregate risk score.
- FRED third-party feeds retain their source licensing and history restrictions. Public accessibility does not grant redistribution rights.
- Household and regional differences are not modeled. Nominal income and spending growth are labeled nominal rather than interpreted as purchasing-power gains.
- No durable local offline cache is added; the default cache is Streamlit's hourly cache. Existing S3 can supply fallback history when explicitly enabled.
- API outages, rate limits and source changes remain possible. The application reports unavailable data; the live audits can be rerun to check current access.
- The EIA core route is narrowly filtered to US residential electricity. Uniquely unfiltered legacy natural-gas and LNG routes are outside the core catalog.
- The separate custom ingestion API is preserved but does not automatically add unreviewed indicators to the household catalog.

## Verified on October 8, 2026

The authenticated audit retrieved usable, within-budget observations for **77 of 77** catalog series. All 76 FRED series returned metadata and their public pages resolved; the EIA US residential electricity route returned observations. FRED metadata exposed a legacy consumer-credit unit error: `TOTALSL` is millions of dollars, corrected in the new catalog. `docs/live-source-audit.json` preserves the point-in-time source metadata and observation results; `docs/source-audit.json` records public-page identity checks.

The ledger retains or corrects 69 legacy rows, consolidates four duplicates and demotes 166 rows. Eight newly selected series bring the distinct active set to 77. This is a catalog refactor, not a claim that 77 independent statistical risk factors exist.
