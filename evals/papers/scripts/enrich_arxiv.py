"""Step 2a: enrich raw pool with arXiv primary categories.

For each paper that has an arXiv ID, fetch its primary category from arxiv.org's
Atom API. Saves data/raw_pool_enriched.json with two new fields per paper:
  - arxiv_primary_category: "cs.LG", "cs.CV", etc. (None if unmappable)
  - subdomain: human label or None
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "data" / "raw_pool.json"
OUT_PATH = ROOT / "data" / "raw_pool_enriched.json"

ARXIV_API = "http://export.arxiv.org/api/query"
BATCH_SIZE = 100
DELAY_SECONDS = 3.0  # arXiv asks for >=3s between calls

CATEGORY_TO_SUBDOMAIN = {
    "cs.LG": "Machine Learning",
    "stat.ML": "Machine Learning",
    "cs.CV": "Computer Vision",
    "cs.CL": "Natural Language Processing",
    "cs.IR": "Information Retrieval",
    "cs.CR": "Computer Security",
    "cs.HC": "Human-Computer Interaction",
}

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def normalize_arxiv_id(raw_id: str) -> str:
    return raw_id.strip()


def fetch_categories_batch(arxiv_ids: list[str]) -> dict[str, str | None]:
    """Returns dict mapping arxiv_id -> primary_category (or None if missing)."""
    params = {
        "id_list": ",".join(arxiv_ids),
        "max_results": str(len(arxiv_ids)),
    }
    resp = requests.get(ARXIV_API, params=params, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    out: dict[str, str | None] = {aid: None for aid in arxiv_ids}
    for entry in root.findall("atom:entry", ATOM_NS):
        id_elem = entry.find("atom:id", ATOM_NS)
        if id_elem is None or not id_elem.text:
            continue
        # ID looks like http://arxiv.org/abs/2007.05864v1
        m = re.search(r"abs/([^v]+?)(v\d+)?$", id_elem.text.strip())
        if not m:
            continue
        aid = m.group(1)
        prim = entry.find("arxiv:primary_category", ATOM_NS)
        if prim is not None:
            out[aid] = prim.attrib.get("term")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not IN_PATH.exists():
        print(f"Missing {IN_PATH}. Run fetch_papers.py first.", file=sys.stderr)
        return 1
    if OUT_PATH.exists() and not args.force:
        print(f"{OUT_PATH} already exists. Use --force to re-enrich.")
        return 0

    raw = json.loads(IN_PATH.read_text())
    papers = raw["papers"]
    arxiv_ids = []
    paper_to_arxiv: dict[str, str] = {}
    for p in papers:
        aid = (p.get("externalIds") or {}).get("ArXiv")
        if aid:
            aid = normalize_arxiv_id(aid)
            paper_to_arxiv[p["paperId"]] = aid
            arxiv_ids.append(aid)

    print(f"Loaded {len(papers)} papers; {len(arxiv_ids)} have arXiv IDs.")
    print(f"Fetching categories in batches of {BATCH_SIZE} with {DELAY_SECONDS}s delay between calls.")

    id_to_cat: dict[str, str | None] = {}
    for i in range(0, len(arxiv_ids), BATCH_SIZE):
        batch = arxiv_ids[i:i + BATCH_SIZE]
        try:
            result = fetch_categories_batch(batch)
        except Exception as e:
            print(f"  batch {i//BATCH_SIZE + 1} failed: {e}", file=sys.stderr)
            for aid in batch:
                id_to_cat[aid] = None
            time.sleep(DELAY_SECONDS)
            continue
        id_to_cat.update(result)
        got = sum(1 for v in result.values() if v)
        print(f"  batch {i//BATCH_SIZE + 1}/{(len(arxiv_ids)+BATCH_SIZE-1)//BATCH_SIZE}: "
              f"{got}/{len(batch)} categories returned (cum {sum(1 for v in id_to_cat.values() if v)})")
        if i + BATCH_SIZE < len(arxiv_ids):
            time.sleep(DELAY_SECONDS)

    enriched = []
    for p in papers:
        pid = p["paperId"]
        aid = paper_to_arxiv.get(pid)
        cat = id_to_cat.get(aid) if aid else None
        sub = CATEGORY_TO_SUBDOMAIN.get(cat) if cat else None
        enriched.append({**p, "arxiv_id": aid, "arxiv_primary_category": cat, "subdomain": sub})

    OUT_PATH.write_text(json.dumps({
        "source": IN_PATH.name,
        "total": len(enriched),
        "papers": enriched,
    }, indent=2))

    from collections import Counter
    cat_counts = Counter(p["arxiv_primary_category"] for p in enriched)
    sub_counts = Counter(p["subdomain"] for p in enriched)
    print(f"\nWrote {len(enriched)} papers to {OUT_PATH}")
    print(f"Top arXiv primary categories:")
    for c, n in cat_counts.most_common(15):
        print(f"  {n:>5}  {c}")
    print(f"\nMapped subdomain distribution:")
    for s, n in sub_counts.most_common():
        print(f"  {n:>5}  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
