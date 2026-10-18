#!/usr/bin/env python3
"""
vault_search.py - lightweight keyword search for the LLM Wiki vault.

No external dependencies. Searches Markdown files, ranks filename/title/body
matches, and prints useful snippets for humans or JSON for agents.
"""

from __future__ import annotations

import argparse
import os
import json
import re
from pathlib import Path


# VAULT_ROOT env wins; default is the kit's own ./vault (one level above scripts/).
VAULT_ROOT = Path(os.environ.get("VAULT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()
SKIP_DIRS = {".obsidian", ".trash", "_meta/scripts/__pycache__"}


def iter_markdown(include_raw: bool = True):
    for path in VAULT_ROOT.rglob("*.md"):
      rel = path.relative_to(VAULT_ROOT)
      parts = set(rel.parts)
      if ".obsidian" in parts or ".trash" in parts:
          continue
      if not include_raw and rel.parts and rel.parts[0] == "_raw":
          continue
      yield path


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def make_snippet(text: str, terms: list[str], radius: int = 90) -> str:
    lower = text.lower()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if not positions:
        return normalize(text[: radius * 2])
    idx = min(positions)
    start = max(0, idx - radius)
    end = min(len(text), idx + radius)
    return ("..." if start else "") + normalize(text[start:end]) + ("..." if end < len(text) else "")


def score_file(rel: str, title: str, body: str, terms: list[str]) -> int:
    hay_rel = rel.lower()
    hay_title = title.lower()
    hay_body = body.lower()
    score = 0
    for term in terms:
        if term in hay_rel:
            score += 12
        if term in hay_title:
            score += 10
        score += hay_body.count(term)
    if all(term in (hay_rel + " " + hay_title + " " + hay_body) for term in terms):
        score += 20
    return score


def search(query: str, limit: int, include_raw: bool) -> list[dict]:
    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9_+-]+", query)]
    if not terms:
        return []

    results = []
    for path in iter_markdown(include_raw=include_raw):
        rel = str(path.relative_to(VAULT_ROOT))
        try:
            body = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        title = first_heading(body) or path.stem
        score = score_file(rel, title, body, terms)
        if score <= 0:
            continue
        results.append({
            "path": rel,
            "title": title,
            "score": score,
            "snippet": make_snippet(body, terms),
        })

    results.sort(key=lambda r: (-r["score"], r["path"]))
    return results[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Search a Markdown knowledge vault")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", "-n", type=int, default=12, help="Maximum results")
    parser.add_argument("--no-raw", action="store_true", help="Exclude _raw/ source files")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    results = search(args.query, args.limit, include_raw=not args.no_raw)

    if args.json:
        print(json.dumps({"query": args.query, "results": results}, indent=2))
        return 0

    print(f"Vault: {VAULT_ROOT}")
    print(f"Query: {args.query}")
    print(f"Results: {len(results)}")
    for i, result in enumerate(results, 1):
        print()
        print(f"{i}. {result['title']} [{result['score']}]")
        print(f"   {result['path']}")
        print(f"   {result['snippet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

