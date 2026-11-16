"""Start this checkout on loopback and validate its real, authenticated views."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_deployment import check_charts, check_http


def main():
    target = json.loads((ROOT / 'monitoring.json').read_text())
    # Fixed loopback target belongs to the child process, never a production URL.
    target.update(site_url='http://127.0.0.1:8512/',
                  health_url='http://127.0.0.1:8512/_stcore/health', health_mode='endpoint')
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Candidate checkout on loopback; not production',
              'commit': os.environ.get('GITHUB_SHA', ''),
              'expected_release': target['expected_release'], 'status': 'failed', 'checks': []}
    process = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'app.py',
        '--server.headless=true', '--server.address=127.0.0.1', '--server.port=8512',
        '--browser.gatherUsageStats=false'], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            if process.poll() is not None:
                break
            try:
                if requests.get(target['health_url'], timeout=2).text.strip() == 'ok':
                    report['checks'] = check_http(target) + check_charts(target)
                    report['status'] = 'passed' if all(c['passed'] for c in report['checks']) else 'failed'
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        else:
            report['checks'] = [{'check': 'candidate_startup', 'passed': False}]
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        Path('candidate-report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
