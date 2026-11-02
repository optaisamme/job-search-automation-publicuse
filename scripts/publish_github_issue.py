"""Post this run's results (new qualifying jobs and near misses) as a GitHub issue.

Runs inside GitHub Actions after `python -m jobsearch outbox prepare`. Uses the
workflow's built-in GITHUB_TOKEN (no personal credentials). GitHub emails repository
watchers about new issues. Delivery outcome is recorded so nothing is posted twice.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jobsearch.store import Store  # noqa: E402


def main() -> int:
    out = json.loads((ROOT / "out/outbox.json").read_text())
    draft = out.get("draft")
    ids = out.get("notification_ids", [])
    if not draft:
        print("No new qualifying jobs or near misses this run; nothing posted.")
        return 0
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    payload = {"title": f"{draft['subject']} ({date.today().isoformat()})", "body": "```text\n" + draft["body"] + "\n```"}
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues", data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "User-Agent": "job-search-automation"})
    store = Store(ROOT / "data/jobs.sqlite")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            issue = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        for nid in ids:
            store.mark_notification(nid, "failed", channel="github_issue", error=str(e)[:300])
        print(f"Could not create the issue ({e}); results will be retried next run.")
        return 1
    for nid in ids:
        store.mark_notification(nid, "delivered", channel="github_issue", ref=str(issue.get("number")))
    print(f"Posted results: {issue.get('html_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
