# Market Risk Explorer — repository context

Product: Boldin Market Risk Explorer. Public deployment repository: `jasonnees/mosaic-intelligence-public`. The original development repository remains private. The active catalog is `risk_catalog.py`, with 77 unique indicators and six household risk domains. `app.py` is the Streamlit entry point.

`risk_data.py` owns source routing, calendar-year transformations and reliability assessment. Never substitute preset signals for missing data or score unavailable observations as neutral. The portfolio view provides planning questions, not generated allocations. Watch rules are descriptive, explicit and uncalibrated.

The default mode is direct public APIs. No AWS dependency is required. Optional `DATA_SOURCE_MODE=s3` supplements history; API revisions take precedence. Preserve existing bucket names and the `us-east-1` default for users of historical archives. Do not provision infrastructure as part of ordinary dashboard work.

`indicators_300.py`, target-range scripts, backfill scripts and legacy dictionaries in `config.py` remain compatibility artifacts. They are not authoritative for the active dashboard. See `docs/indicator-migration.csv` for all legacy dispositions.

Run `python -m pytest -q`. Authenticated live audits are optional and separate from offline CI; do not print keys or full request exceptions. Check source names, units, frequency, source rights and source-specific history limits before adding indicators.

`indicator_guidance.py` defines specific interpretations and cautions for every active series. Direction describes changes in displayed values, not forecast risk. Keep complete catalog coverage and comparison-history validation. `brand.py` and `.streamlit/config.toml` provide the Boldin light theme; preserve the original Mosaic wordmark as an archival asset.
