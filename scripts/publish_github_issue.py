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



def fenced(text: str) -> str:
    """Wrap untrusted job text in a code block that the text itself cannot close: the fence is longer
    than any run of backticks inside it, so links and @mentions in job text are not activated."""
    import re
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"

def main() -> int:
    out = json.loads((ROOT / "out/outbox.json").read_text())
    draft = out.get("draft")
    ids = out.get("notification_ids", [])
    if not draft:
        print("No new qualifying jobs or near misses this run; nothing posted.")
        return 0
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    payload = {"title": f"{draft['subject']} ({date.today().isoformat()})", "body": fenced(draft["body"])}
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
    (ROOT / "out/issue_url.txt").write_text(issue.get("html_url") or "")
    print(f"Posted results: {issue.get('html_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
