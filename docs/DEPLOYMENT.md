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

Open **Actions → Live monitoring → Run workflow** after merging the monitoring workflow into `main`. It also runs on pushes to main and daily at 13:23 UTC. Scheduled Actions are best effort and can be delayed; this is a daily check, not continuous uptime monitoring. Ensure GitHub Actions failure notifications are enabled for your account.

The two independent jobs check:

- Every catalog entry using authenticated APIs, requiring fresh observations under the existing frequency-specific budgets, successful FRED metadata and complete catalog coverage. Missing credentials fail immediately. A triggered market watch rule is not an operational failure.
- The configured deployed page and plain `ok` Streamlit health response, then a real Chromium browser opening all 11 configured chart views and requiring drawn data lines. The browser supports the Community Cloud iframe and direct-server layout, waits for each run to finish, and rejects stale charts or application exceptions. This checks chart pages, not every series or interaction; offline regressions cover all history ranges and catalog rows. Missing app keys, empty charts or application exceptions fail the browser check.

Each run saves timestamped JSON reports as Actions artifacts for 30 days, including failed runs. Reports in `docs/` remain historical evidence and are not silently rewritten by monitoring. Offline CI remains independent and credential free. A green offline test does not mean production is healthy, and a `not_deployed` report does not verify availability.

For local diagnostics:

```sh
pip install -r requirements-monitoring.txt
python -m playwright install chromium
python scripts/audit_live_sources.py --strict --output live-source-audit.json
python scripts/check_deployment.py --output deployment-report.json
```

The deployment command exits 2 for `not_deployed`, 1 for failure and 0 for success. `--http-only` is a diagnostic mode and reports `http_only`, not full success. The scheduled workflow always includes browser checks when deployed. Freshness budgets are observation-age heuristics, not official release calendars; a delayed release inside its budget can still pass.

## Current deployment

[Open Market Risk Explorer](https://mosaic-intelligence-public-fxeuzgnmvbhihv8cchxjaj.streamlit.app/).
`monitoring.json` records this owner-provided target and its verified server health
route. The older `mosaic-intelligence.streamlit.app` hostname is a different
deployment and must not be substituted for this target. The outer Community Cloud
page can return HTML with HTTP 200 even at the wrong health path; a health check
requires the literal `ok` response, followed separately by browser chart checks.

### Community Cloud health verification

This deployment uses `health_mode: browser`: its public `/_stcore/health` route returns the HTML shell instead of `ok`, and `/~/+/_stcore/health` returns HTTP 400. Neither is a valid standalone liveness probe. Monitoring requires HTTP availability **and** the expected app title, completed execution, no app exceptions, and a populated chart on every configured view. A shell/login page alone never passes. `--http-only` is incomplete and exits 2 in browser mode. Direct servers can retain endpoint mode with a verified health URL.
