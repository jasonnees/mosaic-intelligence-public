# Isolated Streamlit frontend preview

This orphan branch contains no dashboard code, production monitoring files or
`.streamlit/` configuration. Its title-and-text app makes no data-source calls.
Do not merge this unrelated-history branch into production.

## Deploy the preview separately

Create a separate Streamlit Community Cloud app from repository
`jasonnees/mosaic-intelligence-public`, branch `preview/minimal-streamlit`,
entry point `app.py`. Choose a new app subdomain and Python 3.14 in advanced
settings. Leave secrets empty. Do not change the existing dashboard deployment.

Open Manage app logs and record the `DIAGNOSTIC_RUNTIME` line, the installed
package list and the deployment time. Python patch versions are managed by
the host, not requirements.txt. Confirm Streamlit 1.66.1 and compare the actual
runtime with production; it previously reported Python 3.14.10. The host may
adjust packages such as PyArrow. Record the resulting environment, not just
the requested dependency. This branch does not claim that a preview is deployed.

## Run a bounded local batch

Use an isolated environment. Install the checker separately from app dependencies:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements-check.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -q
.venv/bin/python paired_check.py --label laptop --runs 3 --timeout 30 --interval 5 \
  https://mosaic-intelligence-public-fxeuzgnmvbhihv8cchxjaj.streamlit.app/ \
  https://YOUR-PREVIEW.streamlit.app/
```

URLs must use HTTPS (local HTTP is accepted for fixture tests), with no embedded
credentials, query or fragment. Two or three distinct URLs are required. A round
loads every app once; the first app rotates each round. Each load uses a fresh,
nonpersistent browser context with service workers blocked. Cookies and browser
cache are not carried between loads. The explicit public wake prompt is supported.

The total per-load deadline covers navigation, wake-up, iframe and title waits;
it does not reset at each stage. Defaults are three rounds, 30 seconds per load,
five seconds between rounds, and a 900-second total batch budget. Allowed bounds
are 1–20 rounds, 10–180 seconds per load and 0–60 seconds between rounds. Start
with a small batch; no recurring schedule or day-long run is installed.

Results append to `results.jsonl`, with a batch ID, location, UTC time, order,
title result, failure stage/type, timings and abnormal or pending network requests.
HTTP 400+ responses and responses lasting at least 10 seconds are retained.
The checker omits URL credentials, queries, fragments, raw exceptions, request
headers and response bodies. It records counts of browser/console errors, without
their potentially sensitive messages. Context shutdown aborts are not counted
as observed failures. A title pass does not establish full dashboard health;
inspect its network records even when the title renders.

Exit 0 means all requested titles rendered; exit 1 means a title failed; exit 2
means the batch budget prevented completion. An incomplete batch is not a pass.

Optionally pass `--metadata runtime-metadata.json` with an object keyed by each
app URL. Values should contain the Python and package versions actually observed
in hosting logs. Without it, app versions are explicitly marked unverified.
Checker-machine versions are recorded separately and do not establish server
versions. Never include API keys or secrets in this metadata.

## Run manually on GitHub

The isolated workflow uses the existing registered path `monitoring.yml` because
GitHub requires the workflow entry to exist on the default branch for dispatch.
The workflow contents here are used only with this explicit preview ref; the
production branch's file is unchanged. The initial preview-branch push runs
fixture tests only, without visiting production or deploying anything.

```sh
gh workflow run monitoring.yml -R jasonnees/mosaic-intelligence-public \
  --ref preview/minimal-streamlit -f mode=fixtures

gh workflow run monitoring.yml -R jasonnees/mosaic-intelligence-public \
  --ref preview/minimal-streamlit -f mode=paired \
  -f preview_url=https://YOUR-PREVIEW.streamlit.app/ \
  -f rounds=3 -f timeout=30 -f interval=5
```

To attach observed runtime/package versions, add
`-F runtime_metadata=@runtime-metadata.json`. The paired job first requires the
fixture tests to pass. Results and environment metadata are uploaded as artifacts.
No secrets, production source changes, production monitor overrides or support
messages are required. The same files can instead be copied to a dedicated
repository's default branch, where the manual workflow is directly available.

## Interpret repeated paired results

A failed preview helps exclude dashboard imports and data calls as necessary
causes. A healthy preview alongside production failures suggests an app,
configuration or deployment-specific difference; it does not prove a bad merge.
Intermittent failures in both suggest a shared delivery/framework/network problem,
not proof of a platform-wide outage. A single successful load is insufficient.

The fixture tests check direct rendering, iframe rendering, wake-up, a stalled
page, an HTTP 500 asset response, cookie isolation, a shared deadline, URL
redaction, command-line ordering/appending/runtime records and oversized-batch
rejection. Fixture success proves checker behavior, not hosted app availability.
