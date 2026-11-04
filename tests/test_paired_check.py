from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
from threading import Thread
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import TimeoutError as BrowserTimeout, sync_playwright

from paired_check import Deadline, TITLE, check_once, main, safe_url


@pytest.fixture(scope="module")
def server():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            status = 200
            body = f"<h1>{TITLE}</h1>"
            if path == "/wrapper":
                body = '<iframe title="streamlitApp" src="/title"></iframe>'
            elif path == "/asleep":
                body = '<button onclick="location.href=\'/wrapper\'">Yes, get this app back up!</button>'
            elif path == "/stalled":
                body = '<p>Loading forever</p>'
            elif path == "/asset":
                body = f'<script src="/broken.js?api_key=DO_NOT_RECORD"></script><h1>{TITLE}</h1>'
            elif path == "/broken.js":
                status, body = 500, "asset unavailable"
            elif path == "/clean" and self.headers.get("Cookie"):
                body = "<h1>Unexpected previous-session cookie</h1>"
            self.send_response(status)
            self.send_header("Content-Type", "text/html")
            if path == "/title":
                self.send_header("Set-Cookie", "preview_probe=present; Path=/")
            self.end_headers()
            self.wfile.write(body.encode())

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    thread.join(timeout=5)
    httpd.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.mark.parametrize("path", ["/title", "/wrapper", "/asleep"])
def test_direct_wrapped_and_sleeping_apps_render(browser, server, path):
    result = check_once(browser, server + path, timeout_seconds=5)
    assert result["passed"], result
    assert result["stage"] == "app_title"


def test_stalled_app_fails(browser, server):
    result = check_once(browser, server + "/stalled", timeout_seconds=0.4)
    assert not result["passed"]
    assert result["error_type"] == "TimeoutError"


def test_asset_500_recorded_even_when_title_renders(browser, server):
    result = check_once(browser, server + "/asset", timeout_seconds=5)
    assert result["passed"]  # This checker proves title rendering, not full health.
    failures = [request for request in result["network"] if request["status"] == 500]
    assert len(failures) == 1
    assert failures[0]["url"] == server + "/broken.js"
    assert "DO_NOT_RECORD" not in json.dumps(result)


def test_sessions_do_not_share_cookies(browser, server):
    assert check_once(browser, server + "/title", timeout_seconds=5)["passed"]
    assert check_once(browser, server + "/clean", timeout_seconds=5)["passed"]


def test_deadline_is_shared_across_stages():
    clock = [100.0]
    deadline = Deadline(10, clock=lambda: clock[0])
    clock[0] = 106.0
    assert deadline.remaining_ms() == 4000
    clock[0] = 111.0
    with pytest.raises(BrowserTimeout):
        deadline.remaining_ms()


def test_recorded_urls_remove_credentials_query_and_fragment():
    assert safe_url("https://user:secret@example.org/static/main.js?token=secret#secret") == "https://example.org/static/main.js"
    assert safe_url("data:text/plain,secret") == "data:[omitted]"


def test_cli_rotates_app_order_appends_results_and_preserves_runtime_metadata(server, tmp_path):
    output = tmp_path / "results.jsonl"
    metadata = tmp_path / "runtime.json"
    first, second = server + "/title", server + "/wrapper"
    metadata.write_text(json.dumps({first: {"python": "3.14.10", "streamlit": "1.66.1"}}))
    args = ["--label", "fixture", "--interval", "0", "--timeout", "10",
            "--output", str(output), "--metadata", str(metadata), first, second]
    script = str(Path(__file__).resolve().parents[1] / "paired_check.py")
    for rounds in ["2", "1"]:
        completed = subprocess.run([sys.executable, script, "--runs", rounds, *args],
                                   capture_output=True, text=True, timeout=60)
        assert completed.returncode == 0, completed.stdout + completed.stderr
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert [row["url"] for row in rows] == [first, second, second, first, first, second]
    assert len({row["batch_id"] for row in rows}) == 2
    assert all(row["passed"] and row["location"] == "fixture" for row in rows)
    assert rows[0]["app_runtime"]["python"] == "3.14.10"
    assert "not supplied" in rows[1]["app_runtime"]["verification"]


def test_cli_rejects_oversized_batches_before_starting_browser():
    with pytest.raises(SystemExit) as error:
        main(["--label", "fixture", "--runs", "21", "https://one.example/", "https://two.example/"])
    assert error.value.code == 2
