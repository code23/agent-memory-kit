#!/usr/bin/env python3
"""Build a compact router index over a set of markdown notes.

The index is the small artifact an agent (or route.py) uses to navigate to the ONE
right note without reading every note body (which burns tokens). Karpathy
"LLM wiki" pattern: the index is already there. Downstream routing is
deterministic lexical retrieval over this metadata; no LLM is required to pick
a title.

Outputs:
  router-index.md   -- lean "Title :: summary" list for deterministic lexical routing
  router-map.json   -- title -> absolute path (this builder); route.py also accepts
                       custom maps with paths relative to the index directory
  router-lint.md    -- notes with weak/missing summaries (fix these to improve routing)

Descriptor per note: frontmatter `summary:` (or `answers:`) if present, else the
first substantive sentence. Curate the frontmatter summaries to make routing bulletproof.

Usage:
  build_index.py --src DIR [DIR ...] [--out OUTDIR]
Defaults to the non-sensitive knowledge scope if --src omitted.
"""
import argparse, json, os, re, sys
from pathlib import Path

# Shared symlink-safe writer lives in funnel/ (sibling of this folder, or the parent of a
# copy of this folder placed inside funnel/).
for _d in (Path(__file__).resolve().parent.parent / "funnel", Path(__file__).resolve().parent.parent):
    if (_d / "safe_io.py").is_file():
        sys.path.insert(0, str(_d))
        break
import safe_io  # noqa: E402

# Default source folders: VAULT_ROOT (env, default ../vault relative to this kit) plus
# the folders below. Override on the command line with --src.
_VAULT = Path(os.environ.get("VAULT_ROOT") or (Path(__file__).resolve().parent.parent / "vault")).expanduser()
DEFAULT_SRC = [
    str(_VAULT / "06-maps"),
    str(_VAULT / "03-resources/agent-systems"),
    str(_VAULT / "03-resources/ai-memory"),
    str(_VAULT / "03-resources/tools"),
]

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
SUMMARY_KEYS = ("summary", "answers", "description")


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if km:
            fm[km.group(1).lower()] = km.group(2).strip().strip('"\'')
    return fm, text[m.end():]


def first_sentence(body):
    for ln in body.splitlines():
        s = re.sub(r"[\*`\[\]#>|]", "", ln).strip()
        if len(s.split()) >= 5 and not s.startswith("- "):
            return s[:220]
    return ""


def descriptor(text):
    fm, body = parse_frontmatter(text)
    for k in SUMMARY_KEYS:
        if fm.get(k):
            return fm[k][:220], True  # curated
    return first_sentence(body), False  # extracted (weaker)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="*", default=DEFAULT_SRC)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    entries, mapping, weak = [], {}, []
    for d in args.src:
        for f in sorted(Path(d).glob("*.md")):
            title = f.stem
            desc, curated = descriptor(f.read_text(errors="ignore"))
            entries.append((title, desc or "(no summary)"))
            if title in mapping:
                print(
                    f"ERROR: duplicate note title {title!r}:\n"
                    f"  first:  {mapping[title]}\n"
                    f"  second: {f}",
                    file=sys.stderr,
                )
                sys.exit(2)
            mapping[title] = str(f.resolve())
            if not curated or not desc:
                weak.append(title)

    # The output directory itself must not be a symlink (checked by safe_io). Its ancestors are
    # the caller's choice of location, so they are not checked (macOS /tmp is itself a symlink).
    safe_io.write_text(out / "router-index.md",
        "# Vault router index (auto-generated)\n\n"
        + "".join(f"- {t} :: {d}\n" for t, d in entries)
    )
    safe_io.write_text(out / "router-map.json", json.dumps(mapping, indent=2))
    safe_io.write_text(out / "router-lint.md",
        "# Router lint\n\n"
        f"{len(entries)} notes indexed. {len(weak)} have weak/auto-extracted summaries "
        "(add a `summary:` frontmatter line to improve routing):\n\n"
        + "".join(f"- {t}\n" for t in weak)
    )

    size = (out / "router-index.md").stat().st_size
    print(f"indexed {len(entries)} notes -> {out/'router-index.md'} ({size} bytes, ~{size//4} tokens)")
    print(f"weak summaries: {len(weak)} (see router-lint.md)")


if __name__ == "__main__":
    main()
