"""Upsert the normalized Doctor intake comment on a GitHub issue."""

from __future__ import annotations

import json
import os
import urllib.request

from community.doctor_issue_intake import MARKER


def _request(method: str, url: str, token: str, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "model-serving-minefield-doctor-intake",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def find_comment_id(comments) -> int | None:
    for comment in comments or []:
        if isinstance(comment, dict) and MARKER in str(comment.get("body") or ""):
            try:
                return int(comment["id"])
            except (KeyError, TypeError, ValueError):
                continue
    return None


def upsert(repo: str, issue_number: int, token: str, body: str) -> str:
    base = f"https://api.github.com/repos/{repo}"
    comments = _request(
        "GET", f"{base}/issues/{issue_number}/comments?per_page=100", token
    )
    existing = find_comment_id(comments)
    if existing is None:
        _request("POST", f"{base}/issues/{issue_number}/comments", token, {"body": body})
        return "created"
    _request("PATCH", f"{base}/issues/comments/{existing}", token, {"body": body})
    return "updated"


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    issue_number = int(os.environ["ISSUE_NUMBER"])
    token = os.environ["GITHUB_TOKEN"]
    path = os.environ["NORMALIZED_COMMENT"]
    with open(path, encoding="utf-8") as fh:
        body = fh.read()
    print(upsert(repo, issue_number, token, body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
