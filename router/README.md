# Vault router (model-free lexical navigation)

A daemon-free, fully-local router that points an agent to the **one** best-matching
note for a question using deterministic lexical retrieval over compact metadata. It is
not an LLM, embeddings store, or network call.

`route.py` ranks `Title :: summary` lines from `router-index.md` and resolves the
chosen title through `router-map.json`. Metadata-only routing never opens note
bodies.

## How it works

1. `build_index.py` builds a compact `router-index.md` (`Title :: summary`) plus
   `router-map.json` (title → path) and `router-lint.md` (notes needing a better
   summary). The builder emits absolute paths; `route.py` also accepts custom maps
   with paths relative to the index directory.
2. `route.py "<question>"` scores title+summary with a small BM25-style ranker
   (stopword filtering, title weighted above summary, exact-title preference) and
   prints `Title<TAB>/absolute/path` on a single clear winner.

## Usage

```bash
python3 build_index.py --src DIR [DIR ...] --out OUTDIR
python3 route.py --indexdir OUTDIR "how should we pick a model"
python3 route.py --indexdir OUTDIR --json --limit 5 "model routing policy"
python3 route.py --indexdir OUTDIR --show --allow-root DIR "exact note title"
```

Successful single-match stdout stays:

```text
Title<TAB>/absolute/path
```

With `--show`, the note body is printed after a blank line (only inside scope).
`--json` and `--show` cannot be combined (would not be valid JSON).

## Limits and failure modes

- **No relevance** → nonzero exit (`NONE: no relevant note found`). Never guesses.
- **Exact top-score ties** → nonzero exit (`AMBIGUOUS`). Refine the query or inspect
  candidates with `--json --limit N`. Ambiguity listings and messages are bounded
  (do not dump every tied title). Scores are explanatory lexical scores, not
  model confidence.
- **`--limit N`** must be in `1..20` (default 5) for JSON candidate lists and
  ambiguity match listings.
- **Malformed / oversized index or map**, duplicate titles (exact JSON keys or
  casefold), or invalid map shapes → clear errors. Paths are never invented;
  every indexed title must exist in the map. Metadata reads are byte-capped;
  non-regular metadata files are rejected.
- **Relative map paths** resolve against `--indexdir`, not the process cwd.
- **`--model`** is rejected: model-free routing no longer uses Ollama.
- Predictable filesystem/path failures surface as clean errors (nonzero, no
  traceback). Titles and paths may not contain null/control characters that
  would corrupt the legacy `Title<TAB>path` line.

## Explicit content scope (`--show`)

`--show` is an explicit content read and **requires** one or more `--allow-root DIR`
flags. When roots are supplied (with or without `--show`), candidates outside those
roots are filtered **before** ranking. Each `--allow-root` must be an existing
directory (validated and resolved once).

Scoped read hygiene (not a hostile multi-user OS sandbox):

- Resolve paths; reject symlink escapes outside allow-roots.
- Reject missing, non-regular, or non-Markdown notes (alias and resolved
  targets must end in `.md`).
- Bound body reads (256 KiB via capped `read`); reject overflow and non-UTF-8.
- Body is validated/read **before** successful metadata is printed, so a failing
  body read never emits a success line on stdout.
- No body is read on a denied path. Missing `--allow-root` with `--show` errors
  with an actionable example.
- Index text is never treated as shell/commands.

## Make descriptors better (see router-lint.md)

Routing quality tracks summary quality. Add a `summary:` frontmatter line to each
note and rebuild. For large corpora, consider hierarchical area indexes.

Governance: metadata routing is read-only over the index artifacts; note bodies are
touched only under explicit `--show` + `--allow-root`. The index is derived and
disposable. Synthetic fixture tests are not real-vault retrieval benchmarks.
