"""
Step 3: Fetch GitHub metadata for every repo discovered in step 1.

Uses GraphQL field aliases to batch ~50 repos per request. With a PAT this
gets us through ~12k repos in under 10 minutes versus ~2.5h via REST.

Resumable: skips repos already present in the output file.

Output: data/gh_metadata.jsonl
  one row per (owner, repo); meta=null when the repo no longer exists.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GH_GRAPHQL = "https://api.github.com/graphql"

REPO_FIELDS = """
    nameWithOwner
    stargazerCount
    forkCount
    pushedAt
    createdAt
    isFork
    isArchived
    isDisabled
    primaryLanguage { name }
    defaultBranchRef { name }
"""


def build_query(batch: list[tuple[str, str]]) -> str:
    parts = []
    for i, (owner, repo) in enumerate(batch):
        # GraphQL string escaping: double-quote strings, backslash-escape " and \
        o = owner.replace("\\", "\\\\").replace('"', '\\"')
        r = repo.replace("\\", "\\\\").replace('"', '\\"')
        parts.append(
            f'r{i}: repository(owner: "{o}", name: "{r}") {{{REPO_FIELDS}}}'
        )
    return "query Batch {\n" + "\n".join(parts) + "\n}"


async def fetch_batch(
    client: httpx.AsyncClient,
    batch: list[tuple[str, str]],
    headers: dict,
    sem: asyncio.Semaphore,
) -> dict[tuple[str, str], dict | None]:
    query = build_query(batch)
    async with sem:
        for attempt in range(3):
            try:
                r = await client.post(
                    GH_GRAPHQL, headers=headers, json={"query": query}, timeout=60
                )
                if r.status_code == 502 or r.status_code == 503:
                    await asyncio.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                payload = r.json()
                break
            except (httpx.HTTPError, json.JSONDecodeError):
                if attempt == 2:
                    return {pair: None for pair in batch}
                await asyncio.sleep(2 ** attempt)
        else:
            return {pair: None for pair in batch}

    data = payload.get("data") or {}
    out = {}
    for i, pair in enumerate(batch):
        out[pair] = data.get(f"r{i}")
    return out


def load_done(out_path: Path) -> set[tuple[str, str]]:
    if not out_path.exists():
        return set()
    done = set()
    with out_path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
                done.add((row["gh_owner"], row["gh_repo"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def normalize_meta(meta: dict | None) -> dict | None:
    """Flatten nested GraphQL fields for downstream simplicity."""
    if meta is None:
        return None
    return {
        "name_with_owner": meta.get("nameWithOwner"),
        "stars": meta.get("stargazerCount"),
        "forks": meta.get("forkCount"),
        "pushed_at": meta.get("pushedAt"),
        "created_at": meta.get("createdAt"),
        "is_fork": meta.get("isFork"),
        "is_archived": meta.get("isArchived"),
        "is_disabled": meta.get("isDisabled"),
        "language": (meta.get("primaryLanguage") or {}).get("name"),
        "default_branch": (meta.get("defaultBranchRef") or {}).get("name"),
    }


async def main_async(args):
    token = os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("GH_TOKEN not set (see .env.example)")

    in_path = Path(args.in_path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Read all (owner, repo) pairs, dedupe
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    with in_path.open() as f:
        for line in f:
            row = json.loads(line)
            key = (row["gh_owner"], row["gh_repo"])
            if key in seen:
                continue
            seen.add(key)
            pairs.append(key)

    done = load_done(out_path)
    todo = [p for p in pairs if p not in done]
    print(f"Total repos: {len(pairs)} | already fetched: {len(done)} | to fetch: {len(todo)}")

    if not todo:
        print("Nothing to do.")
        return

    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "taste-engine/0.1",
    }
    sem = asyncio.Semaphore(args.concurrency)

    # Append-mode write so we never lose progress on crash
    f_out = out_path.open("a")
    pbar = tqdm(total=len(todo), desc="GraphQL", unit=" repos")

    batches = [todo[i : i + args.batch_size] for i in range(0, len(todo), args.batch_size)]

    async with httpx.AsyncClient() as client:
        # First batch alone, to check headers & cost before parallelizing
        first = await fetch_batch(client, batches[0], headers, sem)
        for (owner, repo), meta in first.items():
            f_out.write(json.dumps({
                "gh_owner": owner, "gh_repo": repo, "meta": normalize_meta(meta),
            }) + "\n")
        f_out.flush()
        pbar.update(len(batches[0]))

        async def worker(batch):
            res = await fetch_batch(client, batch, headers, sem)
            for (owner, repo), meta in res.items():
                f_out.write(json.dumps({
                    "gh_owner": owner, "gh_repo": repo, "meta": normalize_meta(meta),
                }) + "\n")
            f_out.flush()
            pbar.update(len(batch))

        await asyncio.gather(*[worker(b) for b in batches[1:]])

    pbar.close()
    f_out.close()
    print(f"Done. Wrote to {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default=str(DATA_DIR / "show_hn.jsonl"))
    ap.add_argument("--out", default=str(DATA_DIR / "gh_metadata.jsonl"))
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
