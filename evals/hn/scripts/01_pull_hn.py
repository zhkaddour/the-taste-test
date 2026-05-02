"""
Step 1+2: Pull Show HN posts from Algolia and extract GitHub repo references.

Algolia returns most recent first and paginates only up to 1000 hits per query
window. To cover a long date range, we walk backwards: each request narrows
the upper-bound timestamp to the oldest item in the previous batch.

Output: data/show_hn.jsonl  (one Show HN per line, only those with a GitHub URL)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from tqdm import tqdm

ALGOLIA = "https://hn.algolia.com/api/v1/search_by_date"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# github.com/<owner>/<repo>  – owner/repo allow letters, digits, _, -, .
GH_RE = re.compile(r"github\.com/([\w\-.]+)/([\w\-.]+)", re.IGNORECASE)
GH_BAD_OWNERS = {"about", "features", "topics", "collections", "trending",
                 "marketplace", "pricing", "search", "settings", "orgs",
                 "sponsors", "explore", "notifications"}


def extract_github(url: str | None, text: str | None) -> tuple[str, str] | None:
    """Try url first, fall back to text body. Return (owner, repo) or None."""
    for s in (url, text):
        if not s:
            continue
        m = GH_RE.search(s)
        if not m:
            continue
        owner, repo = m.group(1), m.group(2)
        if owner.lower() in GH_BAD_OWNERS:
            continue
        if "gist" in s.lower():
            continue
        repo = repo.rstrip(".git").rstrip("/")
        if not repo or repo.startswith("."):
            continue
        return owner, repo
    return None


async def fetch_window(client: httpx.AsyncClient, lo: int, hi: int) -> list[dict]:
    r = await client.get(ALGOLIA, params={
        "tags": "show_hn",
        "numericFilters": f"created_at_i>={lo},created_at_i<{hi}",
        "hitsPerPage": 1000,
    })
    r.raise_for_status()
    return r.json().get("hits", [])


async def pull_all(start_iso: str, end_iso: str) -> list[dict]:
    """Walk backwards through the date range until exhausted."""
    lo = int(datetime.fromisoformat(start_iso).replace(tzinfo=timezone.utc).timestamp())
    hi = int(datetime.fromisoformat(end_iso).replace(tzinfo=timezone.utc).timestamp())
    seen: dict[str, dict] = {}

    pbar = tqdm(desc="Algolia hits", unit=" posts")
    async with httpx.AsyncClient(timeout=30) as client:
        upper = hi
        while upper > lo:
            hits = await fetch_window(client, lo, upper)
            if not hits:
                break
            for h in hits:
                seen[h["objectID"]] = h
            pbar.update(len(hits))
            new_upper = min(h["created_at_i"] for h in hits)
            if new_upper >= upper:  # safety: no progress
                break
            upper = new_upper
    pbar.close()
    return list(seen.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2020-01-01", help="ISO date (UTC)")
    ap.add_argument("--end", default="2024-01-01", help="ISO date (UTC), exclusive")
    ap.add_argument("--out", default=str(DATA_DIR / "show_hn.jsonl"))
    args = ap.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    out_path = Path(args.out)

    print(f"Pulling Show HN from {args.start} to {args.end}...")
    hits = asyncio.run(pull_all(args.start, args.end))
    print(f"Got {len(hits)} unique Show HN posts")

    kept = 0
    with out_path.open("w") as f:
        for h in hits:
            gh = extract_github(h.get("url"), h.get("story_text"))
            if gh is None:
                continue
            owner, repo = gh
            row = {
                "hn_id": h["objectID"],
                "title": h.get("title") or "",
                "url": h.get("url") or "",
                "story_text": h.get("story_text") or "",
                "points": h.get("points") or 0,
                "num_comments": h.get("num_comments") or 0,
                "author": h.get("author") or "",
                "created_at_i": h["created_at_i"],
                "gh_owner": owner,
                "gh_repo": repo,
            }
            f.write(json.dumps(row) + "\n")
            kept += 1

    print(f"Wrote {kept} GitHub-linked posts to {out_path}")
    print(f"  Drop rate: {(1 - kept/max(len(hits),1)):.1%}")


if __name__ == "__main__":
    main()
