"""Step 1: pull NeurIPS CS paper pool from Semantic Scholar (one or more year ranges).

Caches result to data/raw_pool.json. Re-run with --force to refetch.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "raw_pool.json"

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
FIELDS = ",".join([
    "paperId", "title", "abstract", "citationCount", "year",
    "venue", "authors", "fieldsOfStudy", "externalIds", "publicationVenue",
])
PAGE_LIMIT = 1000
DEFAULT_YEARS = "2010-2015,2020"


def parse_year_specs(spec: str) -> list[str]:
    return [s.strip() for s in spec.split(",") if s.strip()]


def fetch_year_spec(year_spec: str) -> list[dict]:
    """Paginate through the bulk endpoint for a single year spec (a year or year range)."""
    all_papers: list[dict] = []
    token: str | None = None
    page = 0
    reported_total: int | None = None

    while True:
        page += 1
        params = {
            "query": "*",
            "year": year_spec,
            "fieldsOfStudy": "Computer Science",
            "venue": "NeurIPS",
            "fields": FIELDS,
        }
        if token:
            params["token"] = token

        start = time.monotonic()
        resp = requests.get(API_URL, params=params, headers={"Accept": "application/json"}, timeout=60)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if not resp.ok:
            raise RuntimeError(f"Semantic Scholar request failed: {resp.status_code} {resp.reason}\n{resp.text}")
        body = resp.json()

        if reported_total is None and isinstance(body.get("total"), int):
            reported_total = body["total"]
            print(f"  [{year_spec}] API reports total: {reported_total}")
        batch = body.get("data") or []
        all_papers.extend(batch)
        next_token = body.get("token")
        print(
            f"  [{year_spec}] page {page}: got {len(batch)} (cum {len(all_papers)}) "
            f"[{elapsed_ms}ms] token={'yes' if next_token else 'none'}"
        )
        if not next_token or not batch or len(batch) < PAGE_LIMIT:
            break
        token = next_token

    return all_papers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-fetch even if cache exists")
    parser.add_argument(
        "--years", default=DEFAULT_YEARS,
        help=f"Comma-separated list of years or year ranges (default: {DEFAULT_YEARS})",
    )
    args = parser.parse_args()

    if OUT_PATH.exists() and not args.force:
        print(f"raw_pool.json already exists at {OUT_PATH}. Use --force to re-fetch.")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    specs = parse_year_specs(args.years)
    print(f"Fetching from Semantic Scholar bulk search for year specs: {specs}")
    print("  query=* fieldsOfStudy=Computer Science venue=NeurIPS")

    merged: dict[str, dict] = {}
    spec_counts: dict[str, int] = {}
    for spec in specs:
        papers = fetch_year_spec(spec)
        spec_counts[spec] = len(papers)
        for p in papers:
            pid = p.get("paperId")
            if pid and pid not in merged:
                merged[pid] = p

    all_papers = list(merged.values())

    OUT_PATH.write_text(json.dumps({
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "yearSpecs": specs,
        "perSpecCounts": spec_counts,
        "total": len(all_papers),
        "papers": all_papers,
    }, indent=2))

    year_counter: Counter = Counter(p.get("year") for p in all_papers)
    with_abstract = sum(1 for p in all_papers if p.get("abstract"))
    with_arxiv = sum(1 for p in all_papers if (p.get("externalIds") or {}).get("ArXiv"))

    print("\n=== Step 1 report ===")
    print(f"Wrote {len(all_papers)} unique papers to {OUT_PATH}")
    print(f"Per-spec fetched (pre-dedupe): {spec_counts}")
    print(f"Papers with abstract: {with_abstract}")
    print(f"Papers with ArXiv ID: {with_arxiv}")
    print("Per-year breakdown:")
    for year, count in sorted(year_counter.items(), key=lambda kv: (kv[0] is None, kv[0])):
        print(f"  {year}: {count}")
    print("\nProceeding to enrichment + filter without manual review (user requested speed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
