#!/usr/bin/env python3
"""Route a question to the best-matching note via deterministic lexical retrieval.

Reads router-index.md ("Title :: summary") and router-map.json (title -> path).
No LLM, embeddings, network, or subprocess, stdlib only.

Usage:
  route.py "how should we pick which model to use"
  route.py --json --limit 5 "..."
  route.py --show --allow-root /path/to/notes "..."
"""
from __future__ import annotations

import argparse
import json
import math
import re
import stat
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

MAX_INDEX_BYTES = 2 * 1024 * 1024
MAX_MAP_BYTES = 2 * 1024 * 1024
MAX_NOTE_BYTES = 256 * 1024
NOTE_READ_CAP = MAX_NOTE_BYTES + 1  # read at most this many bytes; reject overflow
MAX_LIMIT = 20
MAX_AMBIGUOUS_TITLES = 10

# Title field weighs heavier than summary in BM25-ish scoring.
TITLE_BOOST = 3.0
EXACT_TITLE_SCORE = 1_000_000.0
K1 = 1.2
B = 0.75

STOPWORDS = frozenset(
    """
    a an the and or but if then else when where what which who whom whose
    how why is are was were be been being am do does did doing done
    to of in on at by for from with as into onto over under about against
    between through during before after above below up down out off again
    further once here there all any both each few more most other some such
    no nor not only own same so than too very can will just should now
    this that these those it its i me my we our you your they them their
    """.split()
)

TOKEN_RE = re.compile(r"[a-z0-9]+")
INDEX_LINE_RE = re.compile(r"^\s*-\s*(.+?)\s*::\s*(.*)$")
# Reject C0 controls (incl. NUL/TAB/LF/CR) that would corrupt Title<TAB>path lines.
_BAD_FIELD_RE = re.compile(r"[\x00-\x1f\x7f]")


class RouterError(Exception):
    """User-facing router failure with exit code."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


def _require_safe_field(label: str, value: str, where: str) -> str:
    if _BAD_FIELD_RE.search(value):
        raise RouterError(
            f"ERROR: {label} contains null or control characters in {where}"
        )
    return value


def _is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _read_bounded(path: Path, limit: int) -> bytes:
    """Read at most limit bytes from a regular file; reject overflow."""
    if not _is_regular_file(path):
        raise RouterError(f"ERROR: not a regular file: {path}")
    try:
        with open(path, "rb") as f:
            data = f.read(limit + 1)
    except OSError as e:
        raise RouterError(f"ERROR: cannot read {path}: {e}") from e
    if len(data) > limit:
        raise RouterError(
            f"ERROR: {path} is too large (exceeds {limit} bytes; read capped)"
        )
    return data


def load_index(idxdir: Path) -> list[tuple[str, str]]:
    path = idxdir / "router-index.md"
    if not path.exists():
        raise RouterError(f"ERROR: missing index file: {path}")
    raw = _read_bounded(path, MAX_INDEX_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise RouterError(f"ERROR: index is not valid UTF-8: {path}") from e

    entries: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = INDEX_LINE_RE.match(line)
        if m:
            title, summary = m.group(1).strip(), m.group(2).strip()
        elif "::" in line:
            left, _, right = line.partition("::")
            title, summary = left.strip().lstrip("- ").strip(), right.strip()
        else:
            raise RouterError(
                f"ERROR: malformed index line {lineno} in {path}: expected "
                f"'Title :: summary'"
            )
        if not title:
            raise RouterError(
                f"ERROR: malformed index line {lineno} in {path}: empty title"
            )
        _require_safe_field("title", title, f"{path} line {lineno}")
        _require_safe_field("summary", summary, f"{path} line {lineno}")
        key = title.casefold()
        if key in seen:
            raise RouterError(
                f"ERROR: duplicate title in index {title!r} "
                f"(lines {seen[key]} and {lineno})"
            )
        seen[key] = lineno
        entries.append((title, summary))
    if not entries:
        raise RouterError(f"ERROR: index has no entries: {path}")
    return entries


def _json_object_pairs_hook(path: Path):
    """Reject exact duplicate JSON keys (json.loads otherwise keeps the last)."""

    def hook(pairs: list[tuple[object, object]]) -> dict:
        out: dict = {}
        for k, v in pairs:
            if k in out:
                raise RouterError(
                    f"ERROR: duplicate exact JSON key {k!r} in {path}"
                )
            out[k] = v
        return out

    return hook


def load_map(idxdir: Path) -> dict[str, str]:
    path = idxdir / "router-map.json"
    if not path.exists():
        raise RouterError(f"ERROR: missing map file: {path}")
    raw = _read_bounded(path, MAX_MAP_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise RouterError(f"ERROR: map is not valid UTF-8: {path}") from e
    try:
        data = json.loads(text, object_pairs_hook=_json_object_pairs_hook(path))
    except RouterError:
        raise
    except json.JSONDecodeError as e:
        raise RouterError(f"ERROR: invalid JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise RouterError(f"ERROR: map must be a JSON object (title -> path): {path}")
    out: dict[str, str] = {}
    folded: dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise RouterError(
                f"ERROR: invalid map shape in {path}: keys and values must be strings"
            )
        if not k.strip():
            raise RouterError(f"ERROR: invalid map shape in {path}: empty title key")
        if not v.strip():
            raise RouterError(
                f"ERROR: invalid map shape in {path}: empty path for title {k!r}"
            )
        _require_safe_field("map title", k, str(path))
        _require_safe_field("map path", v, str(path))
        fk = k.casefold()
        if fk in folded:
            raise RouterError(
                f"ERROR: ambiguous duplicate titles in map: {folded[fk]!r} and {k!r}"
            )
        folded[fk] = k
        out[k] = v
    return out


def resolve_map_path(raw: str, idxdir: Path) -> Path:
    """Resolve a map path against the index directory (not cwd). Never invent paths."""
    try:
        p = Path(raw)
    except (ValueError, TypeError) as e:
        raise RouterError(f"ERROR: malformed map path {raw!r}: {e}") from e
    if not p.is_absolute():
        p = idxdir / p
    return p


def validate_allow_roots(raw_roots: list[str]) -> list[Path]:
    """Require each --allow-root to be an existing directory; resolve once."""
    roots: list[Path] = []
    for raw in raw_roots:
        _require_safe_field("allow-root", raw, "--allow-root")
        try:
            p = Path(raw)
        except (ValueError, TypeError) as e:
            raise RouterError(f"ERROR: malformed --allow-root {raw!r}: {e}") from e
        try:
            resolved = p.resolve()
        except (OSError, RuntimeError) as e:
            raise RouterError(f"ERROR: cannot resolve --allow-root {raw!r}: {e}") from e
        if not resolved.is_dir():
            raise RouterError(
                f"ERROR: --allow-root must be an existing directory: {raw}"
            )
        roots.append(resolved)
    return roots


def under_allow_roots(path: Path, roots: list[Path]) -> bool:
    """True if resolved path stays under one of the (already-resolved) allow-roots."""
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    for root_r in roots:
        if resolved == root_r or root_r in resolved.parents:
            return True
    return False


def filter_by_roots(
    candidates: list[tuple[str, str, Path]], roots: list[Path]
) -> list[tuple[str, str, Path]]:
    return [c for c in candidates if under_allow_roots(c[2], roots)]


def bm25_scores(
    query_tokens: list[str], docs: list[tuple[list[str], list[str]]]
) -> list[float]:
    """BM25 over title (boosted) + summary fields. Deterministic."""
    if not query_tokens or not docs:
        return [0.0] * len(docs)

    n = len(docs)
    df: Counter[str] = Counter()
    title_lens: list[int] = []
    summ_lens: list[int] = []
    for title_toks, summ_toks in docs:
        title_lens.append(len(title_toks) or 1)
        summ_lens.append(len(summ_toks) or 1)
        for t in set(title_toks) | set(summ_toks):
            df[t] += 1

    avg_title = sum(title_lens) / n
    avg_summ = sum(summ_lens) / n
    scores: list[float] = []
    for i, (title_toks, summ_toks) in enumerate(docs):
        tc, sc = Counter(title_toks), Counter(summ_toks)
        score = 0.0
        for term in query_tokens:
            if df[term] == 0:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            ft = tc.get(term, 0)
            fs = sc.get(term, 0)
            if ft:
                score += (
                    idf
                    * TITLE_BOOST
                    * (ft * (K1 + 1))
                    / (ft + K1 * (1 - B + B * title_lens[i] / avg_title))
                )
            if fs:
                score += (
                    idf
                    * (fs * (K1 + 1))
                    / (fs + K1 * (1 - B + B * summ_lens[i] / avg_summ))
                )
        scores.append(score)
    return scores


def explain_score(
    query_tokens: list[str], title: str, summary: str, score: float, exact: bool
) -> str:
    title_hits = sorted(set(tokenize(title)) & set(query_tokens))
    summ_hits = sorted(set(tokenize(summary)) & set(query_tokens))
    parts = [f"lexical={score:.4f}"]
    if exact:
        parts.append("exact_title=true")
    if title_hits:
        parts.append("title_hits=" + ",".join(title_hits))
    if summ_hits:
        parts.append("summary_hits=" + ",".join(summ_hits))
    if not title_hits and not summ_hits and not exact:
        parts.append("no_token_overlap")
    return "; ".join(parts)


def absolute_display_path(path: Path) -> str:
    """Absolute path for output without inventing a note. Prefer resolve when present."""
    try:
        if path.exists():
            return str(path.resolve())
        return str(path if path.is_absolute() else path.absolute())
    except (OSError, RuntimeError, ValueError):
        return str(path)


def rank(question: str, entries: list[tuple[str, str, Path]]) -> list[dict]:
    """Return ranked candidate dicts with explanatory scores. Deterministic order."""
    q_norm = " ".join(question.split()).casefold()
    q_tokens = tokenize(question)
    docs = [(tokenize(t), tokenize(s)) for t, s, _ in entries]
    raw_scores = bm25_scores(q_tokens, docs)

    ranked: list[dict] = []
    for i, (title, summary, path) in enumerate(entries):
        exact = title.casefold() == q_norm
        score = EXACT_TITLE_SCORE if exact else raw_scores[i]
        if score <= 0:
            continue
        ranked.append(
            {
                "title": title,
                "path": absolute_display_path(path),
                "path_obj": path,
                "score": score,
                "exact": exact,
                "why": explain_score(q_tokens, title, summary, score, exact),
            }
        )
    ranked.sort(key=lambda r: (-r["score"], r["title"].casefold(), r["path"]))
    return ranked


def _require_markdown_suffix(path: Path, label: str) -> None:
    if not path.name.lower().endswith(".md"):
        raise RouterError(f"ERROR: {label} is not Markdown (.md): {path}")


def read_note_body(path: Path) -> str:
    """Strict, bounded note read. Rejects non-md / non-regular / oversized / non-UTF8."""
    _require_markdown_suffix(path, "note")
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError) as e:
        raise RouterError(f"ERROR: cannot resolve note path {path}: {e}") from e
    _require_markdown_suffix(resolved, "resolved note")
    if not _is_regular_file(resolved):
        # Distinguishes missing vs non-regular after resolve.
        if not resolved.exists():
            raise RouterError(f"ERROR: note does not exist: {path}")
        raise RouterError(f"ERROR: note is not a regular file: {path}")
    try:
        with open(resolved, "rb") as f:
            data = f.read(NOTE_READ_CAP)
    except OSError as e:
        raise RouterError(f"ERROR: cannot read note {path}: {e}") from e
    if len(data) > MAX_NOTE_BYTES:
        raise RouterError(
            f"ERROR: note exceeds {MAX_NOTE_BYTES} bytes while reading: {path}"
        )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise RouterError(f"ERROR: note is not valid UTF-8: {path}") from e


def build_candidates(
    entries: list[tuple[str, str]], mapping: dict[str, str], idxdir: Path
) -> list[tuple[str, str, Path]]:
    """Join index entries to map paths. Never invent a path."""
    by_fold = {k.casefold(): (k, v) for k, v in mapping.items()}
    out: list[tuple[str, str, Path]] = []
    missing: list[str] = []
    for title, summary in entries:
        hit = by_fold.get(title.casefold())
        if not hit:
            missing.append(title)
            continue
        _map_title, raw = hit
        out.append((title, summary, resolve_map_path(raw, idxdir)))
    if missing:
        raise RouterError(
            "ERROR: index titles missing from map (never inventing paths): "
            + ", ".join(repr(t) for t in missing[:10])
            + ("…" if len(missing) > 10 else "")
        )
    return out


def format_legacy(hit: dict) -> str:
    return f"{hit['title']}\t{hit['path']}"


def _format_ambiguous_titles(tied: list[dict]) -> str:
    shown = tied[:MAX_AMBIGUOUS_TITLES]
    titles = ", ".join(repr(r["title"]) for r in shown)
    extra = len(tied) - len(shown)
    if extra > 0:
        titles += f", … (+{extra} more)"
    return titles


def _match_payload(r: dict) -> dict:
    return {
        "title": r["title"],
        "path": r["path"],
        "score": r["score"],
        "why": r["why"],
    }


def _fs_to_router(exc: BaseException) -> RouterError:
    return RouterError(f"ERROR: filesystem/path failure: {exc}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Deterministic lexical note router (model-free)."
    )
    ap.add_argument("question", help="question or note title to route")
    ap.add_argument(
        "--indexdir",
        default=str(HERE),
        help="directory with router-index.md and router-map.json",
    )
    ap.add_argument(
        "--show",
        action="store_true",
        help="print note body (requires --allow-root; incompatible with --json)",
    )
    ap.add_argument(
        "--allow-root",
        action="append",
        default=[],
        metavar="DIR",
        help="repeatable allow-root; filters candidates before ranking; required with --show",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="print bounded candidate metadata as JSON (incompatible with --show)",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=5,
        metavar="N",
        help=f"max candidates in --json / ambiguity listings (1..{MAX_LIMIT}, default 5)",
    )
    ap.add_argument(
        "--model",
        default=None,
        help="rejected: model-free routing no longer uses Ollama",
    )
    args = ap.parse_args(argv)

    if args.model is not None:
        print(
            "ERROR: --model is not supported. Model-free routing no longer uses "
            "Ollama (or any LLM/embeddings). Remove --model and retry.",
            file=sys.stderr,
        )
        return 2

    if args.json and args.show:
        print(
            "ERROR: --json and --show cannot be combined (JSON metadata plus raw "
            "Markdown is not valid JSON). Use --json for candidates, or --show "
            "with --allow-root for a single note body.",
            file=sys.stderr,
        )
        return 2

    if args.limit < 1 or args.limit > MAX_LIMIT:
        print(
            f"ERROR: --limit must be between 1 and {MAX_LIMIT} (got {args.limit})",
            file=sys.stderr,
        )
        return 2

    if args.show and not args.allow_root:
        print(
            "ERROR: --show requires at least one --allow-root DIR so note bodies "
            "are only read inside an explicit repeatable scope. Example:\n"
            '  route.py --show --allow-root /path/to/notes "your question"',
            file=sys.stderr,
        )
        return 2

    try:
        idxdir = Path(args.indexdir)
    except (ValueError, TypeError) as e:
        print(f"ERROR: malformed --indexdir: {e}", file=sys.stderr)
        return 2

    try:
        if not idxdir.is_dir():
            print(f"ERROR: --indexdir is not a directory: {idxdir}", file=sys.stderr)
            return 2
    except OSError as e:
        print(f"ERROR: cannot access --indexdir {idxdir}: {e}", file=sys.stderr)
        return 2

    try:
        roots = validate_allow_roots(args.allow_root) if args.allow_root else None
    except RouterError as e:
        print(str(e), file=sys.stderr)
        return e.code

    try:
        entries = load_index(idxdir)
        mapping = load_map(idxdir)
        candidates = build_candidates(entries, mapping, idxdir)
        if roots is not None:
            candidates = filter_by_roots(candidates, roots)
        ranked = rank(args.question, candidates)
    except RouterError as e:
        print(str(e), file=sys.stderr)
        return e.code
    except (OSError, ValueError, RuntimeError) as e:
        print(str(_fs_to_router(e)), file=sys.stderr)
        return 2

    if not ranked:
        payload = {
            "status": "none",
            "matches": [],
            "message": "no relevant note found",
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("NONE: no relevant note found", file=sys.stderr)
        return 2

    top = ranked[0]
    tied = [r for r in ranked if r["score"] == top["score"]]
    if len(tied) > 1:
        titles = _format_ambiguous_titles(tied)
        payload = {
            "status": "ambiguous",
            "matches": [_match_payload(r) for r in tied[: args.limit]],
            "message": f"ambiguous top-score tie between {titles}",
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(
                f"AMBIGUOUS: top-score tie between {titles}; "
                "refine the query or use --json --limit N",
                file=sys.stderr,
            )
        return 2

    body: str | None = None
    if args.show:
        path_obj: Path = top["path_obj"]
        if roots is None or not under_allow_roots(path_obj, roots):
            print(
                f"ERROR: refused to read note outside --allow-root scope: {path_obj}",
                file=sys.stderr,
            )
            return 2
        try:
            body = read_note_body(path_obj)
        except RouterError as e:
            print(str(e), file=sys.stderr)
            return e.code
        except (OSError, ValueError, RuntimeError) as e:
            print(str(_fs_to_router(e)), file=sys.stderr)
            return 2

    if args.json:
        limited = ranked[: args.limit]
        payload = {
            "status": "ok",
            "matches": [_match_payload(r) for r in limited],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(format_legacy(top))
        if body is not None:
            print("\n" + body)

    return 0


if __name__ == "__main__":
    sys.exit(main())
