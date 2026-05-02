#!/usr/bin/env python3
"""
Taste Test server — serves repo root as static files and provides two API endpoints:
  GET  /api/personas     → list all personas (id, name, bio, priors, has_rich_doctrine)
  POST /api/evaluate     → body: {idea, personas: [id,...]}
                        → {evaluations: [{persona_id, persona_name, verdict, headline, reasoning}]}

Usage:
  ANTHROPIC_API_KEY=sk-... python web/server.py [port]
  then open http://localhost:4318/web/
"""
from __future__ import annotations

import sys
import pathlib

# Auto-activate .venv so this works with any python3 invocation
_venv_site = pathlib.Path(__file__).resolve().parents[1] / ".venv" / "lib"
for _sp in _venv_site.glob("python*/site-packages"):
    if str(_sp) not in sys.path:
        sys.path.insert(0, str(_sp))

import base64
import concurrent.futures
import io
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Load .env from repo root if present
_env_file = Path(__file__).resolve().parents[1] / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

PORT = 4318
REPO_ROOT = Path(__file__).resolve().parents[1]
DOCTRINES_DIR = REPO_ROOT / "doctrines"
PLAYBOOKS_JSON_DIR = DOCTRINES_DIR / "_playbooks_json"

JSON_STEM_TO_PID = {
    "altman":     "sam_altman",
    "andreessen": "marc_andreessen",
    "balaji":     "balaji_srinivasan",
    "buffett":    "warren_buffett",
    "cathie":     "cathie_wood",
    "dalio":      "ray_dalio",
    "graham":     "paul_graham",
    "hamming":    "richard_hamming",
    "jensen":     "jensen_huang",
    "karpathy":   "andrej_karpathy",
    "marks":      "howard_marks",
    "munger":     "charlie_munger",
    "musk":       "elon_musk",
    "naval":      "naval_ravikant",
    "rand":       "ayn_rand",
    "soros":      "george_soros",
    "taleb":      "nassim_taleb",
    "thiel":      "peter_thiel",
}

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 350

VERDICT_ORDER = {"strong_yes": 0, "yes": 1, "neutral": 2, "no": 3, "strong_no": 4}

def _claude(api_key: str, messages: list, max_tokens: int = MAX_TOKENS) -> str:
    import anthropic as _anthropic
    client = _anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(model=MODEL, max_tokens=max_tokens, messages=messages)
    return resp.content[0].text.strip()

COMPARE_PROMPT = """\
You are channeling {name}'s perspective. Their {label}:
{profile}

Compare these ideas and pick the one most worth pursuing. Be opinionated — there is always a best answer.

{idea_blocks}

Valid labels: {labels}. The "winner" field must be exactly one of these labels — a single letter only, never "Idea A" or anything else.

Return JSON only — no preamble or fences:
{{"winner": "<single label letter>", "ranking": ["<best>", "<second>", ...], "verdicts": {{"<label>": "one punchy sentence in their voice for each idea"}}}}"""


def load_personas() -> dict[str, dict]:
    personas: dict[str, dict] = {}

    for pdir in sorted(DOCTRINES_DIR.iterdir()):
        if not pdir.is_dir() or pdir.name.startswith("_"):
            continue
        prof_file = pdir / "profile.json"
        if not prof_file.exists():
            continue
        p = json.loads(prof_file.read_text())
        pid = p["persona_id"]
        personas[pid] = {
            "persona_id": pid,
            "name": p["name"],
            "bio": p.get("bio", ""),
            "priors": p.get("priors", []),
            "has_rich_doctrine": False,
            "format": "json",
            "profile_text": json.dumps(p, indent=2),
        }

    # Load structured JSON playbooks (preferred over markdown)
    for jfile in sorted(PLAYBOOKS_JSON_DIR.glob("*.json")):
        pid = JSON_STEM_TO_PID.get(jfile.stem)
        if pid and pid in personas:
            doctrine = json.loads(jfile.read_text())
            personas[pid]["doctrine_json"] = doctrine
            personas[pid]["has_rich_doctrine"] = True
            # Build a plain-text profile for the LLM prompts
            parts = [f"{personas[pid]['name']} — {doctrine.get('summary', '')}"]
            for layer in doctrine.get("layers", []):
                parts.append(f"\n{layer['name']}:")
                for d in layer.get("doctrines", [])[:8]:
                    parts.append(f"  • {d['name']}: {d['rule']}")
            personas[pid]["profile_text"] = "\n".join(parts)
            personas[pid]["format"] = "json"

    return personas


PERSONAS = load_personas()


def extract_pdf_text(b64_data: str) -> str:
    try:
        from pypdf import PdfReader
        pdf_bytes = base64.b64decode(b64_data)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages) if pages else "[PDF had no extractable text]"
    except Exception as exc:
        return f"[PDF extraction failed: {exc}]"

EVAL_PROMPT = """\
You are channeling {name}'s perspective to evaluate an idea. Use their priors and voice — be direct and specific.

Their {label}:
{profile}

Idea to evaluate:
{idea}{context_block}

Return JSON only, no preamble:
{{"verdict": "strong_yes" | "yes" | "neutral" | "no" | "strong_no", "headline": "one punchy sentence reaction in their voice", "reasoning": "2-3 sentences of their specific take, referencing their actual framework and priors"}}"""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def log_message(self, fmt, *args):  # noqa: D102
        pass  # suppress default access log noise

    def do_OPTIONS(self):  # noqa: D102
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: D102
        if self.path == "/api/personas":
            self._handle_personas()
        elif self.path.startswith("/api/doctrine/"):
            pid = self.path[len("/api/doctrine/"):]
            self._handle_doctrine(pid)
        else:
            super().do_GET()

    def do_PATCH(self):  # noqa: D102
        if self.path.startswith("/api/persona/"):
            pid = self.path[len("/api/persona/"):]
            self._handle_patch_persona(pid)
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: D102
        if self.path == "/api/evaluate":
            self._handle_evaluate()
        elif self.path == "/api/compare":
            self._handle_compare()
        else:
            self.send_error(404)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_personas(self):
        safe = [
            {k: v for k, v in p.items() if k not in ("profile_text", "format")}
            for p in PERSONAS.values()
        ]
        self._json(200, safe)

    def _handle_patch_persona(self, pid: str):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            persona = PERSONAS.get(pid)
            if not persona:
                self._json(404, {"error": "Persona not found"})
                return
            prof_file = DOCTRINES_DIR / pid / "profile.json"
            if not prof_file.exists():
                self._json(404, {"error": "Profile file not found"})
                return
            profile = json.loads(prof_file.read_text())
            if "bio" in body:
                profile["bio"] = body["bio"]
                persona["bio"] = body["bio"]
            if "priors" in body:
                profile["priors"] = [p for p in body["priors"] if p.strip()]
                persona["priors"] = profile["priors"]
            prof_file.write_text(json.dumps(profile, indent=2))
            self._json(200, {"ok": True})
        except Exception as exc:
            self._json(500, {"error": str(exc)})

    def _handle_doctrine(self, pid: str):
        persona = PERSONAS.get(pid)
        if not persona or not persona.get("has_rich_doctrine"):
            self._json(404, {"error": "No doctrine found"})
            return
        if "doctrine_json" in persona:
            self._json(200, {"format": "json", "data": persona["doctrine_json"]})
        else:
            self._json(200, {"format": "markdown", "markdown": persona["profile_text"]})

    def _handle_evaluate(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            idea = body.get("idea", "").strip()
            context = body.get("context", "").strip()
            pdf_b64 = body.get("pdf_b64", "")
            if pdf_b64:
                context = extract_pdf_text(pdf_b64)
            requested = body.get("personas", list(PERSONAS.keys()))

            if not idea:
                self._json(400, {"error": "idea is required"})
                return

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                self._json(500, {"error": "ANTHROPIC_API_KEY environment variable is not set"})
                return

            context_block = (
                f"\n\nAdditional context / attached file:\n{context[:4000]}"
                if context else ""
            )

            def evaluate_one(pid: str) -> dict | None:
                persona = PERSONAS.get(pid)
                if not persona:
                    return None
                label = "playbook" if persona["format"] == "markdown" else "profile"
                prompt = EVAL_PROMPT.format(
                    name=persona["name"],
                    label=label,
                    profile=persona["profile_text"],
                    idea=idea,
                    context_block=context_block,
                )
                text = _claude(api_key, [{"role": "user", "content": prompt}])
                if text.startswith("```"):
                    text = text.strip("`")
                    if text.lower().startswith("json"):
                        text = text[4:]
                    text = text.strip()
                parsed = json.loads(text)
                return {
                    "persona_id": pid,
                    "persona_name": persona["name"],
                    "has_rich_doctrine": persona["has_rich_doctrine"],
                    "verdict": parsed.get("verdict", "neutral"),
                    "headline": parsed.get("headline", ""),
                    "reasoning": parsed.get("reasoning", ""),
                }

            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                futures = {ex.submit(evaluate_one, pid): pid for pid in requested}
                for fut in concurrent.futures.as_completed(futures):
                    r = fut.result()
                    if r:
                        results.append(r)

            results.sort(key=lambda r: VERDICT_ORDER.get(r.get("verdict", "neutral"), 2))
            self._json(200, {"evaluations": results})

        except Exception as exc:
            self._json(500, {"error": str(exc)})

    def _handle_compare(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            raw_ideas = body.get("ideas", [])
            pdf_b64s = body.get("pdf_b64s", [])
            requested = body.get("personas", list(PERSONAS.keys()))

            # Append extracted PDF text to each idea that has one
            ideas = []
            for i, txt in enumerate(raw_ideas):
                txt = txt.strip()
                if not txt:
                    continue
                if i < len(pdf_b64s) and pdf_b64s[i]:
                    extracted = extract_pdf_text(pdf_b64s[i])
                    txt += f"\n\nAttached document:\n{extracted[:3000]}"
                ideas.append(txt)

            if len(ideas) < 2:
                self._json(400, {"error": "At least two ideas required"})
                return
            if len(ideas) > 5:
                ideas = ideas[:5]

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                self._json(500, {"error": "ANTHROPIC_API_KEY environment variable is not set"})
                return

            import random
            labels = ["A", "B", "C", "D", "E"][: len(ideas)]

            def compare_one(pid: str) -> dict | None:
                persona = PERSONAS.get(pid)
                if not persona:
                    return None

                # Randomise presentation order to eliminate position bias
                shuffled = list(range(len(ideas)))
                random.shuffle(shuffled)
                prompt_labels = ["A", "B", "C", "D", "E"][: len(ideas)]
                idea_blocks = "\n\n".join(
                    f"Idea {prompt_labels[j]}:\n{ideas[shuffled[j]]}"
                    for j in range(len(ideas))
                )
                # Map prompt label → canonical label
                prompt_to_canonical = {prompt_labels[j]: labels[shuffled[j]] for j in range(len(ideas))}

                label = "playbook" if persona["format"] == "markdown" else "profile"
                prompt = COMPARE_PROMPT.format(
                    name=persona["name"],
                    label=label,
                    labels=", ".join(prompt_labels),
                    profile=persona["profile_text"],
                    idea_blocks=idea_blocks,
                )
                text = _claude(api_key, [{"role": "user", "content": prompt}], max_tokens=400)
                if text.startswith("```"):
                    text = text.strip("`")
                    if text.lower().startswith("json"):
                        text = text[4:]
                    text = text.strip()
                parsed = json.loads(text)

                def resolve(lbl):
                    lbl = lbl.strip().upper()
                    if lbl.startswith("IDEA "):
                        lbl = lbl[5:].strip()
                    return prompt_to_canonical.get(lbl)

                winner_prompt = parsed.get("winner", "")
                winner = resolve(winner_prompt)
                if not winner:
                    for r in parsed.get("ranking", []):
                        winner = resolve(r)
                        if winner:
                            break
                if not winner:
                    winner = labels[0]

                # Remap verdicts back to canonical labels
                verdicts = {
                    prompt_to_canonical.get(k.strip().upper(), k): v
                    for k, v in parsed.get("verdicts", {}).items()
                }

                return {
                    "persona_id": pid,
                    "persona_name": persona["name"],
                    "winner": winner,
                    "verdicts": verdicts,
                }

            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                futures = {ex.submit(compare_one, pid): pid for pid in requested}
                for fut in concurrent.futures.as_completed(futures):
                    r = fut.result()
                    if r:
                        results.append(r)

            # Build tally: first-place votes per idea
            vote_counts = {lbl: [] for lbl in labels}
            for r in results:
                vote_counts.get(r["winner"], vote_counts[labels[0]]).append(r["persona_name"])

            tally = sorted(
                [{"label": lbl, "text": ideas[i], "first_place": len(voters), "voters": voters}
                 for i, (lbl, voters) in enumerate(vote_counts.items())],
                key=lambda x: -x["first_place"],
            )

            results.sort(key=lambda r: labels.index(r["winner"]) if r["winner"] in labels else 99)
            self._json(200, {"results": results, "tally": tally})

        except Exception as exc:
            self._json(500, {"error": str(exc)})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"The Taste Test  →  http://localhost:{port}/web/")
    print(f"Loaded {len(PERSONAS)} personas  ({sum(1 for p in PERSONAS.values() if p['has_rich_doctrine'])} with rich doctrines)")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠  ANTHROPIC_API_KEY not set — Taste Test tab will be disabled")
    server = HTTPServer(("", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
