"""Bounded title-only comparisons. Does not establish full dashboard health."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from playwright.sync_api import TimeoutError as BrowserTimeout, sync_playwright

TITLE = "Boldin Market Risk Explorer"


def safe_url(url):
    """Retain a diagnostic path, never credentials, query values or fragments."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        return parsed.scheme + ":[omitted]"
    host = parsed.hostname or ""
    if ":" in host:
        host = "[" + host + "]"
    if parsed.port:
        host += ":" + str(parsed.port)
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


class Deadline:
    def __init__(self, seconds, clock=time.monotonic):
        self.clock = clock
        self.end = clock() + seconds

    def remaining_ms(self):
        remaining = self.end - self.clock()
        if remaining <= 0:
            raise BrowserTimeout("Load deadline exceeded")
        return max(1, int(remaining * 1000))


def check_once(browser, url, timeout_seconds=30):
    started = time.monotonic()
    deadline = Deadline(timeout_seconds)
    context = browser.new_context(service_workers="block")
    page = context.new_page()
    requests_seen = {}
    page_errors, console_errors = [], []
    stage, passed, error_type = "page_load", False, None

    def requested(request):
        requests_seen[request] = {
            "url": safe_url(request.url), "resource_type": request.resource_type,
            "started": time.monotonic(), "outcome": "pending", "status": None,
        }

    def responded(response):
        entry = requests_seen.get(response.request)
        if entry is not None:
            entry["status"] = response.status
            entry["headers_seconds"] = round(time.monotonic() - entry["started"], 3)

    def finished(request, outcome):
        entry = requests_seen.get(request)
        if entry is not None:
            entry["outcome"] = outcome
            entry["seconds"] = round(time.monotonic() - entry["started"], 3)
            if outcome == "failed":
                # Browser failure text can include request URLs. Retain only net codes.
                code = re.match(r"net::ERR_[A-Z0-9_]+", request.failure or "")
                entry["error"] = code.group(0) if code else "request_failed"

    page.on("request", requested)
    page.on("response", responded)
    page.on("requestfinished", lambda request: finished(request, "finished"))
    page.on("requestfailed", lambda request: finished(request, "failed"))
    page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
    page.on("console", lambda message: console_errors.append(True) if message.type == "error" else None)
    surface = """() => document.querySelector('iframe[title="streamlitApp"]')
      || [...document.querySelectorAll('h1')].some(h => h.textContent.trim() === 'Boldin Market Risk Explorer')
      || [...document.querySelectorAll('button')].some(b => b.textContent.trim() === 'Yes, get this app back up!')"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=deadline.remaining_ms())
        stage = "app_surface_or_wake"
        page.wait_for_function(surface, timeout=deadline.remaining_ms())
        wake = page.get_by_role("button", name="Yes, get this app back up!", exact=True)
        if wake.count():
            stage = "wake_app"
            wake.click(timeout=deadline.remaining_ms())
        stage = "app_surface"
        page.wait_for_function("""() => document.querySelector('iframe[title="streamlitApp"]')
          || [...document.querySelectorAll('h1')].some(h => h.textContent.trim() === 'Boldin Market Risk Explorer')""",
          timeout=deadline.remaining_ms())
        app = page.frame_locator('iframe[title="streamlitApp"]') if page.locator('iframe[title="streamlitApp"]').count() else page
        stage = "app_title"
        app.get_by_role("heading", name=TITLE, exact=True).wait_for(state="visible", timeout=deadline.remaining_ms())
        passed = True
    except Exception as error:
        error_type = type(error).__name__
    finally:
        # Capture before closing the context; shutdown itself aborts pending requests.
        observed = time.monotonic()
        network = []
        for entry in requests_seen.values():
            item = {key: value for key, value in entry.items() if key != "started"}
            item.setdefault("seconds", round(observed - entry["started"], 3))
            if (item["outcome"] != "finished" or (item["status"] or 0) >= 400 or item["seconds"] >= 10):
                network.append(item)
        context.close()
    return {"url": safe_url(url), "checked_at": datetime.now(timezone.utc).isoformat(),
            "passed": passed, "stage": stage, "error_type": error_type,
            "duration_seconds": round(time.monotonic() - started, 3),
            "page_error_count": len(page_errors), "console_error_count": len(console_errors),
            "network": network}


def valid_url(value):
    parsed = urlsplit(value)
    local = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not ((parsed.scheme == "https" or local) and parsed.hostname) or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError("Use HTTPS (or local HTTP), without credentials, query or fragment")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+", type=valid_url)
    parser.add_argument("--label", required=True)
    parser.add_argument("--runs", type=int, default=3, help="Rounds; every round loads each app once")
    parser.add_argument("--timeout", type=int, default=30, help="One total deadline per app load, in seconds")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between rounds")
    parser.add_argument("--budget", type=int, default=900, help="Overall batch budget, in seconds")
    parser.add_argument("--output", default="results.jsonl")
    parser.add_argument("--metadata", help="Optional JSON of observed app runtime/package versions, keyed by URL")
    args = parser.parse_args(argv)
    if not 2 <= len(args.urls) <= 3 or len(set(args.urls)) != len(args.urls):
        parser.error("Supply two or three distinct app URLs")
    if not (1 <= args.runs <= 20 and 10 <= args.timeout <= 180 and 0 <= args.interval <= 60 and 10 <= args.budget <= 900):
        parser.error("runs: 1–20; timeout: 10–180; interval: 0–60; budget: 10–900")
    metadata = json.loads(Path(args.metadata).read_text()) if args.metadata else {}
    if not isinstance(metadata, dict):
        parser.error("Runtime metadata must be a JSON object keyed by app URL")
    batch_id = uuid4().hex
    end = time.monotonic() + args.budget
    count, failures, complete = 0, 0, True
    with sync_playwright() as playwright, Path(args.output).open("a") as output:
        browser = playwright.chromium.launch()
        try:
            for round_index in range(args.runs):
                # Rotate the first app each round, to avoid consistently favoring one.
                offset = round_index % len(args.urls)
                ordered = args.urls[offset:] + args.urls[:offset]
                for position, url in enumerate(ordered):
                    remaining = end - time.monotonic()
                    if remaining < 1:
                        complete = False
                        break
                    result = check_once(browser, url, min(args.timeout, remaining))
                    result.update(batch_id=batch_id, location=args.label, round=round_index + 1,
                                  order=position + 1, timeout_seconds=min(args.timeout, round(remaining, 3)),
                                  checker_runtime={"python": sys.version.split()[0], "playwright": version("playwright")},
                                  app_runtime=metadata.get(url, {"verification": "not supplied; verify hosting logs"}))
                    output.write(json.dumps(result) + "\n")
                    output.flush()
                    count += 1
                    failures += not result["passed"]
                    print(json.dumps({key: result[key] for key in ["url", "location", "round", "passed", "stage", "error_type"]}), flush=True)
                if not complete:
                    break
                if round_index + 1 < args.runs:
                    time.sleep(max(0, min(args.interval, end - time.monotonic())))
        finally:
            browser.close()
    complete = complete and count == args.runs * len(args.urls)
    print(json.dumps({"batch_id": batch_id, "completed": count, "expected": args.runs * len(args.urls),
                      "failures": failures, "complete": complete}))
    return 2 if not complete else 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
