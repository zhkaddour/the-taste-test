"""
Step 6: Produce a neutral, anonymized ~200-word abstract for every repo,
combining the HN pitch and README. Removes identifiers and success metrics
that could leak the answer to a downstream persona.

Uses Claude Sonnet 4.6 for the abstractor (this is the security boundary of
the whole eval — leakage here invalidates everything). System prompt is
cached to keep cost low across the run.

Resumable: appends to data/abstracts.jsonl, skips already-done repos.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an anonymizing technical abstractor. Given a Hacker News pitch and a project README, produce a single ~200-word neutral abstract describing:
  1. What problem does this address?
  2. What's the proposed approach?
  3. How does it work technically?

You MUST strip ALL of the following completely:

IDENTIFIERS
- Project name, company name, organization, any trademark
- Founder, author, team, contributor names
- Usernames, handles
- URLs, domain names, repository paths
- Distinctive product/feature branding (replace with generic descriptors like "the tool", "the library", "the system", "the framework")

SUCCESS / TRACTION SIGNALS
- User counts, download counts, star counts, fork counts
- Funding amounts, investor names, customer logos, sponsor mentions
- Press mentions, awards, conference talks, podcast appearances
- "Used by X companies", "trusted by", "powering"
- Version numbers indicating maturity (v2+, "stable", "production-ready", "battle-tested", "1.0+")

VOICE / HYPE
- First-person founder voice ("I built", "we made", "our team") → third-person neutral
- Subjective hype ("revolutionary", "blazingly fast", "the best", "amazing", "game-changing")
- Comparison-to-competitor language ("better than X", "unlike Y")

PRESERVE
- The substantive technical and conceptual content
- The problem framing (what gap, what use case)
- The technical approach (architecture, algorithms, data flow)
- Concrete technical details (languages, protocols, formats) when they don't reveal identity

Output: a single paragraph, ~200 words, third-person, neutral technical tone. Begin directly with the description — no preamble, no headings, no bullet points."""


def collect_inputs(pairs_path: Path, readmes_path: Path) -> dict[tuple[str, str], dict]:
    """Build a dict of (owner, repo) -> {hn_title, hn_text, readme}."""
    # READMEs
    readmes: dict[tuple[str, str], str] = {}
    with readmes_path.open() as f:
        for line in f:
            r = json.loads(line)
            readmes[(r["gh_owner"], r["gh_repo"])] = r.get("readme") or ""

    # HN pitch from pairs (already deduped)
    pitch: dict[tuple[str, str], dict] = {}
    with pairs_path.open() as f:
        for line in f:
            p = json.loads(line)
            for side in ("winner", "loser"):
                s = p[side]
                key = (s["gh_owner"], s["gh_repo"])
                if key in pitch:
                    continue
                pitch[key] = {
                    "hn_title": s["hn_title"],
                    "hn_text": s["hn_story_text"],
                    "readme": readmes.get(key, ""),
                }
    return pitch


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


def build_user_message(payload: dict) -> str:
    title = payload["hn_title"] or "(no title)"
    text = payload["hn_text"] or "(no body)"
    readme = payload["readme"] or "(no README)"
    return (
        f"=== HACKER NEWS PITCH ===\n"
        f"Title: {title}\n\n"
        f"Body:\n{text}\n\n"
        f"=== README ===\n"
        f"{readme}\n"
    )


async def abstract_one(
    client: AsyncAnthropic,
    payload: dict,
    sem: asyncio.Semaphore,
) -> str | None:
    async with sem:
        for attempt in range(3):
            try:
                resp = await client.messages.create(
                    model=MODEL,
                    max_tokens=400,
                    system=[
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[
                        {"role": "user", "content": build_user_message(payload)}
                    ],
                )
                return resp.content[0].text.strip()
            except Exception as e:
                if attempt == 2:
                    print(f"  failed after retries: {e}", file=sys.stderr)
                    return None
                await asyncio.sleep(2 ** attempt)
    return None


async def main_async(args):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set")

    pairs_path = Path(args.pairs)
    readmes_path = Path(args.readmes)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    inputs = collect_inputs(pairs_path, readmes_path)
    done = load_done(out_path)
    todo = [k for k in inputs if k not in done]
    print(f"Total repos: {len(inputs)} | already abstracted: {len(done)} | to do: {len(todo)}")
    if args.limit:
        todo = todo[: args.limit]
        print(f"  (limiting to first {args.limit})")
    if not todo:
        return

    client = AsyncAnthropic(api_key=api_key)
    sem = asyncio.Semaphore(args.concurrency)
    f_out = out_path.open("a")
    pbar = tqdm(total=len(todo), desc="Abstracting", unit=" repos")

    async def worker(key):
        owner, repo = key
        text = await abstract_one(client, inputs[key], sem)
        f_out.write(json.dumps({
            "gh_owner": owner,
            "gh_repo": repo,
            "abstract": text,
        }) + "\n")
        f_out.flush()
        pbar.update(1)

    await asyncio.gather(*[worker(k) for k in todo])

    pbar.close()
    f_out.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(DATA_DIR / "pairs.jsonl"))
    ap.add_argument("--readmes", default=str(DATA_DIR / "readmes.jsonl"))
    ap.add_argument("--out", default=str(DATA_DIR / "abstracts.jsonl"))
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0,
                    help="If >0, only abstract this many (for spot-check).")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
