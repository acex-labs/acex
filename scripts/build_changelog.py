#!/usr/bin/env python3
"""Build the structured changelog (changelog.json) served by the ACEX API.

Pipeline:
  1. git cliff --context  -> structured release/commit data (local git only)
  2. transform            -> our schema (version, date, entries with title,
                             description, group, breaking, pr, commit, urls)
  3. --enrich             -> fill missing descriptions from GitHub PR bodies

The markdown CHANGELOG.md (plain `git cliff`) stays the repo-facing artifact;
this JSON is the API-facing one.

Usage:
  python scripts/build_changelog.py [--since v6.20.0^] [--enrich] [--dry-run] [--repo owner/name]
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

DEFAULT_OUTPUT = "backend/src/acex/changelog.json"
DEFAULT_SINCE = "v6.20.0^"          # history cutoff — pre-6.20.0 is out of scope
FALLBACK_REPO = "acex-labs/acex"

PR_REF_RE = re.compile(r"\(#(\d+)\)")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def detect_repo() -> str:
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
        if m:
            return m.group(1)
    except subprocess.CalledProcessError:
        pass
    return FALLBACK_REPO


def clean_body(body: str) -> str | None:
    """Same rules as the cliff template: drop commit-list bullets,
    Co-authored-by trailers and '---------' separators."""
    kept = [
        line for line in body.split("\n")
        if not line.startswith("* ")
        and "Co-authored-by" not in line
        and not line.startswith("---")
    ]
    text = "\n".join(kept).strip()
    return text or None


def fetch_pr_body(repo: str, number: int, token: str | None) -> str | None:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/pulls/{number}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "acex-changelog-builder",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.load(resp).get("body") or ""
    except Exception as exc:  # 404 / rate limit / network — skip, never fail the run
        print(f"  warning: PR #{number}: {exc}", file=sys.stderr)
        return None
    body = HTML_COMMENT_RE.sub("", body).replace("\r\n", "\n").strip()
    return body or None


def transform_entry(commit: dict, repo_url: str) -> dict:
    message = commit.get("message", "")
    subject = message.split("\n", 1)[0].strip()

    pr_match = PR_REF_RE.search(subject)
    pr = int(pr_match.group(1)) if pr_match else None
    title = PR_REF_RE.sub("", subject).strip()
    if title and title[0].islower():
        title = title[0].upper() + title[1:]

    sha = commit.get("id", "")
    return {
        "title": title,
        "description": clean_body(commit.get("body") or ""),
        "group": commit.get("group") or "Other",
        "breaking": bool(commit.get("breaking")),
        "pr": pr,
        "commit": sha[:7],
        "pr_url": f"{repo_url}/pull/{pr}" if pr else None,
        "commit_url": f"{repo_url}/commit/{sha}" if sha else None,
    }


def transform(context: list[dict], repo_url: str) -> dict:
    releases = []
    for rel in context:
        if rel.get("version") is None:   # "Unreleased" — only tagged releases are shown
            continue
        ts = rel.get("timestamp")
        releases.append({
            "version": rel["version"].lstrip("v"),
            "date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat() if ts else None,
            "entries": [transform_entry(c, repo_url) for c in rel.get("commits", [])],
        })
    return {"releases": releases}


def main() -> None:
    args = sys.argv[1:]
    enrich = "--enrich" in args
    dry_run = "--dry-run" in args
    args = [a for a in args if a not in ("--enrich", "--dry-run")]

    since = DEFAULT_SINCE
    if "--since" in args:
        i = args.index("--since")
        since = args[i + 1]
        del args[i : i + 2]

    repo = FALLBACK_REPO
    if "--repo" in args:
        i = args.index("--repo")
        repo = args[i + 1]
        del args[i : i + 2]
    else:
        repo = detect_repo()

    output = args[0] if args else DEFAULT_OUTPUT

    ctx = subprocess.run(
        ["git", "cliff", "--context", f"{since}..HEAD"],
        capture_output=True, text=True, check=True,
    )
    changelog = transform(json.loads(ctx.stdout), f"https://github.com/{repo}")

    stats = {"entries": 0, "described": 0, "enriched": 0}
    for rel in changelog["releases"]:
        for entry in rel["entries"]:
            stats["entries"] += 1
            if entry["description"]:
                stats["described"] += 1

    if enrich:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            print("warning: GITHUB_TOKEN not set — unauthenticated API is limited to 60 requests/hour", file=sys.stderr)
        for rel in changelog["releases"]:
            for entry in rel["entries"]:
                if entry["description"] is None and entry["pr"] is not None:
                    body = fetch_pr_body(repo, entry["pr"], token)
                    if body:
                        entry["description"] = body
                        stats["enriched"] += 1

    if dry_run:
        print(json.dumps(changelog["releases"][0], indent=2)[:2000] if changelog["releases"] else "no releases")
    else:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(changelog, f, indent=2, ensure_ascii=False)
            f.write("\n")

    print(
        f"releases: {len(changelog['releases'])}, entries: {stats['entries']}, "
        f"local descriptions: {stats['described']}, enriched: {stats['enriched']}"
    )


if __name__ == "__main__":
    main()