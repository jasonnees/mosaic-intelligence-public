# Deploy and monitor Market Risk Explorer

## Deploy with Streamlit Community Cloud

1. Open https://share.streamlit.io/ and sign in with GitHub. Allow access to this repository.
2. Select **Create app**, then deploy from GitHub. Select repository `jasonnees/mosaic-intelligence-public`, branch `main`, and main file `app.py`. A GitHub repository URL is the source location, not the running dashboard URL.
3. In **Advanced settings**, choose Python 3.11 and add the following top-level secrets using your own keys:

   ```toml
   FRED_API_KEY = "your FRED key"
   EIA_API_KEY = "your EIA key"
   DATA_SOURCE_MODE = "api"
   ```

   Top-level Streamlit secrets are exposed as environment variables, which the existing app reads. Obtain keys from https://fred.stlouisfed.org/docs/api/api_key.html and https://www.eia.gov/opendata/register.php. Do not commit keys or paste them in chat.
4. Click **Deploy**. Copy the resulting `https://…streamlit.app` URL. Open the app and check the overview, domain navigation and populated charts.
5. Configure `monitoring.json` with the actual `site_url`, `deployment_status: deployed`, `health_mode: browser`, and all `chart_views` for Community Cloud (see below). For a direct Streamlit server, omit `health_mode` and supply a verified `health_url` that returns `ok`. Example for a direct server:

   ```json
   {
     "deployment_status": "deployed",
     "site_url": "https://YOUR-ACTUAL-APP.streamlit.app",
     "health_url": "https://YOUR-ACTUAL-APP.streamlit.app/~/+/_stcore/health",
     "chart_views": ["Overview", "Inflation risk", "Housing conditions"]
   }
   ```

A fresh repository explicitly starts as `not_deployed`. The deployment check records that state and fails the hosted deployment job until a verified target is configured; it cannot claim production health. GitHub Pages cannot run this Python/Streamlit app. An external login page or sleeping app is not a successful deployment check; inspect the hosted app if monitoring cannot open it.

Official instructions: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy and https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management.

## Enable independent live feed checks

In this repository, open **Settings → Secrets and variables → Actions → New repository secret** and add `FRED_API_KEY` and `EIA_API_KEY`. These are separate from Streamlit deployment secrets: Actions tests the APIs independently, while the deployed app uses its own configuration.

Open **Actions → Source monitoring → Run workflow** for authenticated feed checks. Scheduled observation checks target weekdays at 17:23 UTC (11:23 CST / 12:23 CDT); Monday also checks FRED metadata and catalog frequency. Manual runs include metadata by default. **Deployment monitoring** independently checks the hosted app daily at 13:23 UTC. Both run on pushes to main. Scheduled Actions are best effort and can be delayed; these are periodic checks, not continuous uptime monitoring.

Before merging, dispatch `monitoring.yml` on the candidate branch with
`validate_candidate: true`. This runs the authenticated catalog audit and starts
that checkout on loopback with a cold cache, then opens all configured views.
Artifacts identify the candidate commit and explicitly distinguish this test
from production. It uses the existing Actions source credentials.

The dashboard shows the public build identifier from `release_info.py`.
`monitoring.json` records the expected release, and production monitoring requires
that exact marker before checking the views. Bump both values for each release.
A healthy older deployment cannot pass the new release check.

Streamlit is pinned to 1.67.0, the version used by the successful authenticated
candidate validation. Updating the dependency file prompts Community Cloud to
resolve the environment again. This is also the supported deployment path for
refreshing a running environment after imported module APIs change. See
[Streamlit's upgrade instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-streamlit).
Production browser failures now retain a screenshot and bounded connection
diagnostics without request URLs or exception text. An exception before the title
fails immediately rather than being mistaken for a slow cold start.

The two independent workflows check:

- Every catalog entry using authenticated APIs and complete, unique catalog coverage. JSON and the job summary distinguish feed status, observation status, metadata status, known limitations and actionable reasons. Missing credentials, exhausted requests, malformed responses, unrelated missing comparisons and overdue observations fail. Documented October CPI comparison gaps retain warnings and unavailable values but do not fail the job. A triggered market watch rule is not an operational failure.
- The configured deployed page and plain `ok` Streamlit health response, then a real Chromium browser opening all 11 configured chart views and requiring drawn data lines. The browser supports the Community Cloud iframe and direct-server layout, waits for each run to finish, and rejects stale charts or application exceptions. This checks chart pages, not every series or interaction; offline regressions cover all history ranges and catalog rows. Missing app keys, empty charts or application exceptions fail the browser check.

Each run saves timestamped JSON reports as Actions artifacts for 30 days, including failed runs. Reports in `docs/` remain historical evidence and are not silently rewritten by monitoring. Offline CI remains independent and credential free. A green offline test does not mean production is healthy, and a `not_deployed` report does not verify availability.

Catalog, CPI and GDP loaders share one FRED client per credential per process,
including concurrent cold starts (at least 0.6 seconds between requests).
The standalone audit uses one client for metadata and observations.
Transient connection errors, timeouts, HTTP 429 and selected
server errors receive at most three attempts. A 429 waits at least 60 seconds;
`Retry-After` can extend the wait up to 120 seconds. Larger waits fail the request
instead of retrying early. Reports include sanitized HTTP status codes and
`fred_requests` attempt, retry and error counts so a recovered throttle remains
visible. Other processes using the same key can still consume the provider quota.

An October 2026 CPI observation may have no usable October 2025 comparison:
[BLS did not collect October 2025 CPI data during the federal shutdown](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi.htm).
The dashboard explains this specific gap when the prior-year observation is
absent. Inflation and direction remain unavailable. Strict monitoring returns
`passed_with_warnings` if no actionable failure exists. Longer history cannot
recreate an unpublished observation. No prior month,
interpolated index or older inflation rate is substituted. Stale observations also
continue to fail. This exemption applies only to October 2026 CPIAUCSL,
CPILFESL and CUSR0000SEHA with an absent October 2025 base; a zero or negative
base, unrelated gap, stale observation or request failure still fails.

ISRATIO uses the [current Census publication](https://www.census.gov/mtis/current/index.html)
and the successor data month's [release schedule](https://www.census.gov/mtis/release_schedule.html).
Electricity uses the EIA release header. Both require a matching observation
month and plausible dates, then allow seven calendar days of operational grace.
Missing or invalid evidence retains the age cutoff and a visible warning.
An optional calendar or archive failure is not itself a feed failure; an overdue
observation still fails. No historical daily failure is rewritten or suppressed.

For local diagnostics:

```sh
pip install -r requirements-monitoring.txt
python -m playwright install chromium
python scripts/audit_live_sources.py --strict --output live-source-audit.json
python scripts/audit_live_sources.py --strict --observations-only --output live-source-audit.json --summary source-summary.md
python scripts/check_deployment.py --output deployment-report.json
```

The deployment command exits 2 for `not_deployed`, 1 for failure and 0 for success. `--http-only` is a diagnostic mode and reports `http_only`, not full success. The scheduled workflow always includes browser checks when deployed. Most freshness budgets remain heuristics; a delayed release inside its budget can still pass. Census and EIA calendar checks cover only the two series described above.

## November 15 monitoring review

[The November 15 run](https://github.com/jasonnees/mosaic-intelligence-public/actions/runs/43752249941)
passed all 11 configured production views and failed the source job. The
[source evidence](monitoring-2026-11-15-source-evidence.json) and
[deployment evidence](monitoring-2026-11-15-deployment-evidence.json) were extracted
from that run's JSON log output without altering the historical results.
Scheduled runs failed daily from November 4 through November 15 at main commit
`a44da5be4c97417cd78b76d96c860bf10233f172`.

The ten source failures comprised five request failures (STLFSI4, NFCI, TDSP,
HSN1F, HOUST), three unavailable CPI comparisons and two observations that were
current under the publishers' schedules (ISRATIO and residential electricity).
Main's diagnostics do not identify the HTTP cause of the five requests. The
[PR #16 branch run](https://github.com/jasonnees/mosaic-intelligence-public/actions/runs/43333080696)
recorded a recovered HTTP 429; this establishes throttling as a real mechanism,
not the proven cause of every earlier failure.

The baseline catalog audit makes 152 FRED calls (metadata and observations for
76 series) before retries. CPI and GDP loaders request 16 and 22 series
respectively, using four workers each. The local changes build on PR #16 commit
`3839b8b513fced14a0cd2f7ec18d66ad487764d4` and close its separate-client gap.

Validation: 178 offline tests pass, including concurrent first access, bounded
429 recovery, Census deadline expiry, precise CPI-gap classification, all 11
configured views through real loaders with synthetic HTTP responses, and dashboard
filtering that separates known gaps from outages and stale observations.
Workflow YAML and embedded Bash parse successfully. Live unauthenticated parser
checks returned Census's November 17 and EIA's November 24 next-release dates.
These checks do not establish authenticated feed health for this patch or prove
that the patch is deployed.

Remaining review limits: the metadata contract checks frequency and required
response fields, not every indicator's units, revision policy or methodology.
Publication-calendar coverage is incomplete. Alert state is not persisted across
runs: known gaps no longer fail daily, but actionable failures keep failing until
resolved. FRED pacing is per process; separate deployments or scripts sharing a
key can still trigger retries. A branch deployment and authenticated source audit
remain rollout checks before treating this patch as production-verified.

## Current deployment

[Open Market Risk Explorer](https://mosaic-intelligence-public-fxeuzgnmvbhihv8cchxjaj.streamlit.app/).
`monitoring.json` records this owner-provided target and its verified server health
route. The older `mosaic-intelligence.streamlit.app` hostname is a different
deployment and must not be substituted for this target. The outer Community Cloud
page can return HTML with HTTP 200 even at the wrong health path; a health check
requires the literal `ok` response, followed separately by browser chart checks.

### Community Cloud health verification

This deployment uses `health_mode: browser`: its public `/_stcore/health` route returns the HTML shell instead of `ok`, and `/~/+/_stcore/health` returns HTTP 400. Neither is a valid standalone liveness probe. Monitoring requires HTTP availability **and** the expected app title, completed execution, no app exceptions, and a populated chart on every configured view. A shell/login page alone never passes. `--http-only` is incomplete and exits 2 in browser mode. Direct servers can retain endpoint mode with a verified health URL.
