"""
Step 5: Fetch the README for every repo that appears in pairs.jsonl.

Uses GitHub REST `/repos/{owner}/{repo}/readme` with the raw-content accept
header so we get plain text directly. The endpoint auto-resolves whatever
README file the repo has (README.md, README.rst, readme, ...).

Resumable: appends to data/readmes.jsonl and skips already-fetched repos.
README content is capped at MAX_CHARS so a few oversized repos don't dominate
LLM cost downstream.
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
GH_API = "https://api.github.com"
MAX_CHARS = 12_000  # ~3k tokens; plenty for an abstractor


def collect_repos(pairs_path: Path) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    with pairs_path.open() as f:
        for line in f:
            p = json.loads(line)
            for side in ("winner", "loser"):
                key = (p[side]["gh_owner"], p[side]["gh_repo"])
                if key not in seen:
                    seen.add(key)
                    out.append(key)
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


async def fetch_one(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    headers: dict,
    sem: asyncio.Semaphore,
) -> str | None:
    """Returns README text, or None if no README/repo missing."""
    url = f"{GH_API}/repos/{owner}/{repo}/readme"
    async with sem:
        for attempt in range(3):
            try:
                r = await client.get(url, headers=headers, timeout=30,
                                     follow_redirects=True)
                if r.status_code == 200:
                    return r.text[:MAX_CHARS]
                if r.status_code in (404, 451):
                    return None
                if r.status_code == 403 and "rate limit" in r.text.lower():
                    # Hard rate limit — surface so user can pause
                    raise RuntimeError("Rate limited; retry later.")
                if r.status_code in (502, 503, 504):
                    await asyncio.sleep(2 ** attempt)
                    continue
                # Anything else: log once and skip
                return None
            except httpx.HTTPError:
                if attempt == 2:
                    return None
                await asyncio.sleep(2 ** attempt)
    return None


async def main_async(args):
    token = os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("GH_TOKEN not set")

    pairs_path = Path(args.pairs)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    repos = collect_repos(pairs_path)
    done = load_done(out_path)
    todo = [r for r in repos if r not in done]
    print(f"Total unique repos in pairs: {len(repos)} | already fetched: {len(done)} | to fetch: {len(todo)}")
    if not todo:
        print("Nothing to do.")
        return

    headers = {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github.raw",
        "User-Agent": "taste-engine/0.1",
    }
    sem = asyncio.Semaphore(args.concurrency)

    f_out = out_path.open("a")
    pbar = tqdm(total=len(todo), desc="READMEs", unit=" repos")
    n_found, n_missing = 0, 0

    async with httpx.AsyncClient() as client:
        async def worker(owner, repo):
            nonlocal n_found, n_missing
            text = await fetch_one(client, owner, repo, headers, sem)
            if text is None:
                n_missing += 1
            else:
                n_found += 1
            f_out.write(json.dumps({
                "gh_owner": owner, "gh_repo": repo, "readme": text,
            }) + "\n")
            f_out.flush()
            pbar.update(1)

        await asyncio.gather(*[worker(o, r) for o, r in todo])

    pbar.close()
    f_out.close()
    print(f"Done. Found: {n_found} | missing: {n_missing}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(DATA_DIR / "pairs.jsonl"))
    ap.add_argument("--out", default=str(DATA_DIR / "readmes.jsonl"))
    ap.add_argument("--concurrency", type=int, default=10)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
