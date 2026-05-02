"""Step 1: pull a multi-domain paper pool from Semantic Scholar.

Each venue is mapped to a domain (e.g., NeurIPS → "Machine Learning"). The fetch
loops over (venue × year_spec), tags every paper with its domain, dedupes by
paperId across venues, and caches the merged result to data/raw_pool.json.

Re-run with --force to refetch.
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
INTER_CALL_SLEEP_S = 1.0  # be polite to Semantic Scholar


# Venue → domain mapping. The domain becomes the cohort key used downstream.
# When adding venues, prefer those with: (a) consistent quality bar (top-tier),
# (b) good abstract coverage in Semantic Scholar, (c) clear discipline anchor.
VENUE_TO_DOMAIN: dict[str, str] = {
    # Machine Learning / AI
    "NeurIPS": "Machine Learning",
    "ICML": "Machine Learning",
    "ICLR": "Machine Learning",
    # Mechanical & Aerospace Engineering
    "Journal of Fluid Mechanics": "Mechanical & Aerospace Engineering",
    "AIAA Journal": "Mechanical & Aerospace Engineering",
    "Journal of Mechanical Design": "Mechanical & Aerospace Engineering",
    # Biology / Life Sciences
    "Cell": "Biology / Life Sciences",
    "Nature": "Biology / Life Sciences",
    "PNAS": "Biology / Life Sciences",
    # Chemistry & Materials Science
    "Journal of the American Chemical Society": "Chemistry & Materials Science",
    "Nature Chemistry": "Chemistry & Materials Science",
    "Advanced Materials": "Chemistry & Materials Science",
    # Physics
    "Physical Review Letters": "Physics",
    "Nature Physics": "Physics",
    # Medicine
    "New England Journal of Medicine": "Medicine",
    "The Lancet": "Medicine",
    "JAMA": "Medicine",
    # Economics
    "American Economic Review": "Economics",
    "Quarterly Journal of Economics": "Economics",
    "Econometrica": "Economics",
    "Journal of Political Economy": "Economics",
}

ALL_DOMAINS = sorted(set(VENUE_TO_DOMAIN.values()))


def parse_specs(spec: str) -> list[str]:
    return [s.strip() for s in spec.split(",") if s.strip()]


def fetch_venue_year(venue: str, year_spec: str) -> list[dict]:
    """Paginate through the bulk endpoint for one (venue, year_spec)."""
    all_papers: list[dict] = []
    token: str | None = None
    page = 0
    reported_total: int | None = None

    while True:
        page += 1
        params = {
            "query": "*",
            "year": year_spec,
            "venue": venue,
            "fields": FIELDS,
        }
        if token:
            params["token"] = token

        start = time.monotonic()
        for attempt in range(3):
            try:
                resp = requests.get(API_URL, params=params,
                                    headers={"Accept": "application/json"}, timeout=60)
                if resp.status_code == 429:
                    backoff = 2 ** attempt * 5
                    print(f"    rate-limited; sleeping {backoff}s")
                    time.sleep(backoff)
                    continue
                if not resp.ok:
                    raise RuntimeError(
                        f"S2 request failed: {resp.status_code} {resp.reason}\n{resp.text[:300]}")
                break
            except requests.RequestException as e:
                if attempt == 2:
                    raise
                print(f"    request error ({e}); retrying")
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError("rate-limited 3x in a row")

        elapsed_ms = int((time.monotonic() - start) * 1000)
        body = resp.json()

        if reported_total is None and isinstance(body.get("total"), int):
            reported_total = body["total"]
        batch = body.get("data") or []
        all_papers.extend(batch)
        next_token = body.get("token")
        tok_marker = "yes" if next_token else "none"
        print(f"    [{venue} | {year_spec}] page {page}: +{len(batch)} "
              f"(cum {len(all_papers)}, reported_total={reported_total}) "
              f"[{elapsed_ms}ms] token={tok_marker}")
        if not next_token or not batch or len(batch) < PAGE_LIMIT:
            break
        token = next_token
        time.sleep(INTER_CALL_SLEEP_S)

    return all_papers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-fetch even if cache exists")
    parser.add_argument(
        "--years", default=DEFAULT_YEARS,
        help=f"Comma-separated list of years or year ranges (default: {DEFAULT_YEARS})",
    )
    parser.add_argument(
        "--venues", default=None,
        help="Comma-separated venue subset; defaults to every venue in VENUE_TO_DOMAIN.",
    )
    parser.add_argument(
        "--list-venues", action="store_true",
        help="Print configured venues by domain and exit.",
    )
    args = parser.parse_args()

    if args.list_venues:
        for dom in ALL_DOMAINS:
            print(f"\n{dom}:")
            for v, d in VENUE_TO_DOMAIN.items():
                if d == dom:
                    print(f"  - {v}")
        return 0

    if OUT_PATH.exists() and not args.force:
        print(f"raw_pool.json already exists at {OUT_PATH}. Use --force to re-fetch.")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    venues = parse_specs(args.venues) if args.venues else list(VENUE_TO_DOMAIN.keys())
    unknown = [v for v in venues if v not in VENUE_TO_DOMAIN]
    if unknown:
        print(f"Unknown venues (not in VENUE_TO_DOMAIN): {unknown}", file=sys.stderr)
        return 1

    year_specs = parse_specs(args.years)
    print(f"Fetching {len(venues)} venues × {len(year_specs)} year specs from Semantic Scholar.")
    print(f"  year specs: {year_specs}")
    print(f"  venues by domain:")
    for dom in ALL_DOMAINS:
        venues_in_dom = [v for v in venues if VENUE_TO_DOMAIN[v] == dom]
        if venues_in_dom:
            print(f"    {dom}: {', '.join(venues_in_dom)}")

    merged: dict[str, dict] = {}
    venue_year_counts: dict[str, int] = {}
    venue_year_totals: dict[str, int] = {}  # the API's reported-total

    for venue in venues:
        domain = VENUE_TO_DOMAIN[venue]
        for spec in year_specs:
            print(f"\n  fetching {venue} ({domain}) for years={spec}")
            papers = fetch_venue_year(venue, spec)
            key = f"{venue}|{spec}"
            venue_year_counts[key] = len(papers)
            for p in papers:
                pid = p.get("paperId")
                if not pid:
                    continue
                # First-seen wins; tag with domain + venue + which year-spec we found it under.
                if pid not in merged:
                    p["_domain"] = domain
                    p["_fetched_via_venue"] = venue
                    p["_fetched_via_year_spec"] = spec
                    merged[pid] = p
            time.sleep(INTER_CALL_SLEEP_S)

    all_papers = list(merged.values())

    OUT_PATH.write_text(json.dumps({
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "yearSpecs": year_specs,
        "venues": venues,
        "venueDomainMap": VENUE_TO_DOMAIN,
        "perVenueYearCounts": venue_year_counts,
        "total": len(all_papers),
        "papers": all_papers,
    }, indent=2))

    # Reporting
    year_counter: Counter = Counter(p.get("year") for p in all_papers)
    domain_counter: Counter = Counter(p.get("_domain") for p in all_papers)
    with_abstract = sum(1 for p in all_papers if p.get("abstract"))

    print("\n=== Step 1 report ===")
    print(f"Wrote {len(all_papers):,} unique papers to {OUT_PATH}")
    print(f"Papers with abstract: {with_abstract:,}")
    print()
    print("Per-domain (deduped):")
    for dom in ALL_DOMAINS:
        n = domain_counter.get(dom, 0)
        if n:
            print(f"  {dom}: {n:,}")
    print()
    print("Per-venue × year-spec (pre-dedupe, raw fetch counts):")
    for k, n in sorted(venue_year_counts.items()):
        print(f"  {k}: {n:,}")
    print()
    print("Per-year (after dedupe):")
    for year, count in sorted(year_counter.items(), key=lambda kv: (kv[0] is None, kv[0])):
        print(f"  {year}: {count:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
