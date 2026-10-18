#!/usr/bin/env python3
"""Capture: extract durable typed candidate facts from prose staging notes.

Reads staging notes, asks a configured model to pull out 0-3 explicit, durable facts per
note (not predictions/opinions/ephemeral run-detail), and writes each as a typed
candidate YAML into candidates/ for the consensus loop to triage.

Extractor is pluggable (MEMORY_EXTRACTOR): "cmd" (default) runs the command in
MEMORY_EXTRACTOR_CMD with the prompt on stdin and expects JSON on stdout, or "ollama"
(optional local HTTP fallback). See docs/judges.md.
"""
import argparse, datetime, hashlib, json, os, re, shutil, subprocess, sys, tempfile, urllib.request, uuid
from pathlib import Path
import yaml

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))
import safe_io  # noqa: E402  (shared symlink-safe writer)
ROOT = Path(os.environ.get("MEMORY_ROOT") or CODE_DIR).expanduser().resolve()
CAND = ROOT / "candidates"
REGISTRY_PATH = ROOT / "registry.yaml"
if not REGISTRY_PATH.is_file() and (CODE_DIR / "registry.example.yaml").is_file():
    REGISTRY_PATH = CODE_DIR / "registry.example.yaml"

# Optional local fallback only, not the default, not required.
OLLAMA = "http://localhost:11434/api/generate"
MODEL = os.environ.get("MEMORY_OLLAMA_MODEL", "llama3")

# Soft cap for very large notes (frontier models handle far more than 4k chars).
# Raise further if needed; do not silently truncate small/medium staging notes.
MAX_BODY_CHARS = 100_000

# Hard cap on facts accepted from any extractor (prompt asks for 0-3).
MAX_FACTS_PER_NOTE = 10

ALLOWED_FACT_TYPES = frozenset({
    "preference", "decision", "workflow", "boundary", "tool", "project_fact",
})

# Fallback when registry.yaml is missing. Prefer registry (aliases + destinations).
# Router globs: 06-maps + 03-resources/{agent-systems,ai-memory,tools}.
#
# NOTE (documented limitation): scope_slug collapses punctuation, so distinct
# scopes that differ only by non-alnum chars (e.g. client:acme.io vs client:acme-io)
# can map to the same captured-*.md file. Acceptable; do not over-engineer.
SCOPE_TARGET_MAP = {
    # prefix / exact scope -> (dir under vault, filename template with {slug})
    "org":      ("03-resources/agent-systems", "captured-{slug}.md"),
    "project:": ("03-resources/agent-systems", "captured-{slug}.md"),
    "client:":  ("03-resources/agent-systems", "captured-{slug}.md"),
    "personal": ("03-resources/ai-memory",     "captured-personal.md"),
}

_REGISTRY_CACHE = None
_REGISTRY_MISSING_WARNED = False


class RegistryConfigError(SystemExit):
    """Fatal registry shape error, exit before any candidate is touched."""


def validate_registry_shape(raw, path=None):
    """Validate registry mapping shape. Raises RegistryConfigError if malformed."""
    where = f" ({path})" if path else ""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise RegistryConfigError(
            f"registry config error{where}: top-level must be a mapping, got {type(raw).__name__}"
        )
    for key in ("aliases", "destinations"):
        if key not in raw or raw[key] is None:
            continue
        val = raw[key]
        if not isinstance(val, dict):
            raise RegistryConfigError(
                f"registry config error{where}: '{key}' must be a mapping of str→str, "
                f"got {type(val).__name__}"
            )
        for k, v in val.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise RegistryConfigError(
                    f"registry config error{where}: '{key}' entries must be str→str "
                    f"(bad entry: {k!r} → {v!r})"
                )
    if "drop_patterns" in raw and raw["drop_patterns"] is not None:
        drops = raw["drop_patterns"]
        if not isinstance(drops, list) or not all(isinstance(x, str) for x in drops):
            raise RegistryConfigError(
                f"registry config error{where}: 'drop_patterns' must be a list of strings"
            )
    return True


def load_registry(force=False):
    """Load registry.yaml (aliases, destinations, drop_patterns). Cached.

    Missing file → empty registry + one warning. Malformed → fatal config error
    BEFORE any candidate is touched.
    """
    global _REGISTRY_CACHE, _REGISTRY_MISSING_WARNED
    if _REGISTRY_CACHE is not None and not force:
        return _REGISTRY_CACHE
    if not REGISTRY_PATH.is_file():
        if not _REGISTRY_MISSING_WARNED:
            print(f"warn: registry.yaml missing at {REGISTRY_PATH}; using empty registry",
                  file=sys.stderr)
            _REGISTRY_MISSING_WARNED = True
        _REGISTRY_CACHE = {"aliases": {}, "destinations": {}, "drop_patterns": []}
        return _REGISTRY_CACHE
    try:
        raw = yaml.safe_load(REGISTRY_PATH.read_text())
    except Exception as e:
        raise RegistryConfigError(
            f"registry config error ({REGISTRY_PATH}): failed to parse YAML: {e}"
        ) from e
    validate_registry_shape(raw, path=str(REGISTRY_PATH))
    raw = raw or {}
    _REGISTRY_CACHE = {
        "aliases": dict(raw.get("aliases") or {}),
        "destinations": dict(raw.get("destinations") or {}),
        "drop_patterns": list(raw.get("drop_patterns") or []),
    }
    return _REGISTRY_CACHE

# Unit-inspectable extraction prompt + JSON schema (shared by all adapters).
PROMPT = """Extract DURABLE, EXPLICIT facts worth remembering long-term from the note below.
Return ONLY a JSON array. Each item: {{"fact":"<explicit statement>","type":"preference|decision|workflow|boundary|tool|project_fact","scope":"personal|org|client:<name>|project:<name>","excerpt":"<the sentence it came from, verbatim>"}}
Rules: only explicit facts actually stated; NO predictions, opinions, guesses, or ephemeral run-detail (timings, "ran X", "checked Y"). If nothing durable, return [].

NOTE ({title}):
{body}

JSON array:"""

FACTS_JSON_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "fact": {"type": "string"},
            "type": {
                "type": "string",
                "enum": ["preference", "decision", "workflow", "boundary", "tool", "project_fact"],
            },
            "scope": {"type": "string"},
            "excerpt": {"type": "string"},
        },
        "required": ["fact", "type", "scope", "excerpt"],
        "additionalProperties": False,
    },
}

# Parallel kind labels for secret redaction (match memory.py / policy.yaml order).
_SECRET_PATTERNS = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    r"\bs[k]-[A-Za-z0-9]{8,}",
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    r"[£$€]\s?\d",
    r"\b\+?\d[\d ]{8,}\d\b",
    r"(github|gitlab)\.com/",
    r"export [A-Z_]{4,}",
    r":\d{4,5}\b",
]
_SECRET_KINDS = ["email", "api_key", "ipv4", "money", "phone", "repo_url", "env_export", "port"]



class ExtractorError(Exception):
    """Raised for adapter/CLI/validation failures, caught by main (not SystemExit)."""


def _policy_path():
    if os.environ.get("MEMORY_POLICY"):
        return Path(os.environ["MEMORY_POLICY"]).expanduser()
    p = ROOT / "policy.yaml"
    return p if p.exists() else CODE_DIR / "policy.example.yaml"


def active_patterns():
    """Built-in patterns plus every forbidden_pattern from the active policy (same file memory.py uses).

    Policy patterns are index-aligned with _SECRET_KINDS; extras get the kind "secret".
    """
    pats, kinds = list(_SECRET_PATTERNS), list(_SECRET_KINDS)
    try:
        pol = yaml.safe_load(_policy_path().read_text()) or {}
        for pat in pol.get("forbidden_patterns") or []:
            if isinstance(pat, str) and pat not in pats:
                pats.append(pat)
                kinds.append("secret")
    except Exception:
        pass
    return pats, kinds


def redact_secrets(text, patterns=None, kinds=None):
    """Replace secret spans with [REDACTED:kind]. Pure; returns (redacted, kinds_hit)."""
    if text is None:
        return "", []
    s = str(text)
    if patterns is None:
        pats, klist = active_patterns()
    else:
        pats, klist = patterns, (kinds if kinds is not None else _SECRET_KINDS)
    hits = []
    for i, pat in enumerate(pats):
        kind = klist[i] if i < len(klist) else "secret"
        try:
            rx = re.compile(pat)
        except re.error:
            continue

        def _sub(m, _kind=kind):
            if _kind not in hits:
                hits.append(_kind)
            return f"[REDACTED:{_kind}]"

        s = rx.sub(_sub, s)
    return s, hits


def scope_slug(scope):
    """Slug a scope for a stable filename (e.g. project:northwind -> project-northwind).

    Documented limitation: distinct scopes that differ only by non-alnum characters
    can collide on the same slug (see SCOPE_TARGET_MAP comment).
    """
    s = re.sub(r"[^a-z0-9]+", "-", str(scope or "personal").lower()).strip("-")
    return s or "personal"


def resolve_alias(scope_or_slug, registry=None):
    """Resolve scope/slug through registry aliases (one hop, exact full-slug keys only)."""
    reg = registry if registry is not None else load_registry()
    slug = scope_slug(scope_or_slug)
    aliases = reg.get("aliases") or {}
    if slug in aliases:
        return aliases[slug]
    return slug


def resolve_destination(canonical_slug, registry=None):
    """Look up vault-relative note path (exact keys only)."""
    reg = registry if registry is not None else load_registry()
    dests = reg.get("destinations") or {}
    return dests.get(canonical_slug)


def _legacy_target_note_for_scope(scope):
    """Pre-registry path convention (fallback when registry misses)."""
    scope = str(scope or "personal").strip()
    if scope == "personal" or scope.startswith("personal"):
        d, tmpl = SCOPE_TARGET_MAP["personal"]
        return f"{d}/{tmpl.format(slug='personal')}"
    if scope == "org" or scope.startswith("org"):
        d, tmpl = SCOPE_TARGET_MAP["org"]
        return f"{d}/{tmpl.format(slug=scope_slug(scope))}"
    if scope.startswith("project:"):
        d, tmpl = SCOPE_TARGET_MAP["project:"]
        return f"{d}/{tmpl.format(slug=scope_slug(scope))}"
    if scope.startswith("client:"):
        d, tmpl = SCOPE_TARGET_MAP["client:"]
        return f"{d}/{tmpl.format(slug=scope_slug(scope))}"
    d, tmpl = SCOPE_TARGET_MAP["personal"]
    return f"{d}/captured-{scope_slug(scope)}.md"


def target_note_for_scope(scope):
    """Map scope to a STABLE router-indexed vault-relative note path via registry.

    Resolves exact full-slug aliases, then exact destinations. Falls back to legacy
    SCOPE_TARGET_MAP when registry has no entry (metadata only at capture time ,
    memory.py parks unknown-scope at triage if the note does not already exist).
    """
    reg = load_registry()
    canonical = resolve_alias(scope, reg)
    dest = resolve_destination(canonical, reg)
    if dest:
        return dest
    return _legacy_target_note_for_scope(scope)


def fact_matches_drop_pattern(fact_text, registry=None):
    """True if fact text matches any registry drop_patterns (run-noise)."""
    reg = registry if registry is not None else load_registry()
    text = str(fact_text or "")
    for pat in reg.get("drop_patterns") or []:
        try:
            if re.search(pat, text):
                return True
        except re.error:
            continue
    return False


def state_path_for(note: Path) -> Path:
    """Sidecar next to the note: <note>.capture-state.json."""
    return Path(str(note) + ".capture-state.json")


def write_capture_state(note: Path, state: str, facts: int = 0, error: str = None,
                        bump_attempts: bool = None, **extra):
    """Write capture-state sidecar.

    attempts: incremented on finished failed/captured unless previous state was
    'running' (reconcile already claimed+incremented this attempt). Pass
    bump_attempts=True/False to override auto behaviour.
    """
    sp = state_path_for(note)
    prev = {}
    if sp.exists():
        try:
            prev = json.loads(sp.read_text()) or {}
        except Exception:
            prev = {}
    attempts = int(prev.get("attempts") or 0)
    if bump_attempts is None:
        # Auto: bump on terminal states unless reconcile already claimed this run.
        if state in ("failed", "captured") and prev.get("state") != "running":
            attempts += 1
    elif bump_attempts:
        attempts += 1
    rec = {
        "state": state,
        "facts": facts,
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": str(note.resolve()) if note.exists() else str(note),
        "attempts": attempts,
        "extractor": resolve_extractor_name(),
    }
    if error:
        rec["error"] = error[:500]
    rec.update(extra)
    safe_io.write_text(sp, json.dumps(rec, indent=2) + "\n", root=ROOT)
    return sp


def resolve_extractor_name():
    """MEMORY_EXTRACTOR env (cmd | ollama), default cmd."""
    return (os.environ.get("MEMORY_EXTRACTOR") or "cmd").strip().lower()


def _require_cli(binary, extractor_name):
    path = shutil.which(binary)
    if not path:
        raise ExtractorError(
            f"MEMORY_EXTRACTOR={extractor_name} requires the '{binary}' CLI, "
            f"but it was not found on PATH. Install it or set MEMORY_EXTRACTOR to an "
            f"available adapter (cmd|ollama). Refusing silent downgrade."
        )
    return path


def _scope_grammar_ok(scope):
    """Scope must match policy grammar: personal | org | client:<name> | project:<name>."""
    s = str(scope or "").strip()
    if s in ("personal", "org"):
        return True
    if s.startswith("client:") and len(s) > len("client:"):
        return True
    if s.startswith("project:") and len(s) > len("project:"):
        return True
    return False


def validate_facts(facts):
    """Validate extractor output. Returns the list or raises ExtractorError.

    Applied to every adapter (cmd/ollama): required keys, string types,
    type enum, scope grammar, excerpt present, item count capped.
    """
    if facts is None:
        return []
    if not isinstance(facts, list):
        raise ExtractorError(f"extractor output is not a list (got {type(facts).__name__})")
    if len(facts) > MAX_FACTS_PER_NOTE:
        # Truncate to the cap rather than discard the whole batch, a fact-rich
        # note should still yield its top facts, not zero. The cap prevents a
        # runaway extraction from flooding the review queue.
        facts = facts[:MAX_FACTS_PER_NOTE]
    cleaned = []
    for i, item in enumerate(facts):
        if not isinstance(item, dict):
            raise ExtractorError(f"fact[{i}] is not an object")
        for key in ("fact", "type", "scope", "excerpt"):
            if key not in item:
                raise ExtractorError(f"fact[{i}] missing required key '{key}'")
            if not isinstance(item[key], str):
                raise ExtractorError(
                    f"fact[{i}].{key} must be a string (got {type(item[key]).__name__})"
                )
        fact = item["fact"].strip()
        ftype = item["type"].strip()
        scope = item["scope"].strip()
        excerpt = item["excerpt"].strip()
        if not fact:
            raise ExtractorError(f"fact[{i}].fact is empty")
        if not excerpt:
            raise ExtractorError(f"fact[{i}].excerpt is empty")
        if ftype not in ALLOWED_FACT_TYPES:
            raise ExtractorError(
                f"fact[{i}].type {ftype!r} not in allowed enum {sorted(ALLOWED_FACT_TYPES)}"
            )
        if not _scope_grammar_ok(scope):
            raise ExtractorError(f"fact[{i}].scope {scope!r} fails scope grammar")
        # drop_patterns: auto-reject run-noise at capture-validation time
        if fact_matches_drop_pattern(fact):
            continue  # skip silently as run-noise (not a hard extractor failure)
        cleaned.append({
            "fact": fact,
            "type": ftype,
            "scope": scope,
            "excerpt": excerpt,
        })
    return cleaned


def _parse_facts_payload(text):
    """Parse model stdout into a list of fact dicts (schema-shaped)."""
    if not text or not str(text).strip():
        return []
    raw = str(text).strip()
    # some CLIs wrap the answer in a JSON envelope
    try:
        obj = json.loads(raw)
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            for key in ("structuredOutput", "text", "result", "content", "output", "response", "facts", "data", "message"):
                if key in obj:
                    inner = obj[key]
                    if isinstance(inner, list):
                        return inner
                    if isinstance(inner, str):
                        return _parse_facts_payload(inner)
            # single fact object
            if "fact" in obj:
                return [obj]
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def extract_facts_cmd(title, body):
    """Pluggable extractor: run MEMORY_EXTRACTOR_CMD (prompt on stdin, JSON on stdout).

    Point it at any model CLI or a small script that calls your provider's API
    (read the key from the environment, never from a file in this repo).
    """
    import shlex
    cmd = (os.environ.get("MEMORY_EXTRACTOR_CMD") or "").strip()
    if not cmd:
        raise ExtractorError("MEMORY_EXTRACTOR_CMD is not set. Refusing silent downgrade.")
    _require_cli(shlex.split(cmd)[0], "cmd")
    prompt = PROMPT.format(title=title, body=body)
    r = subprocess.run(shlex.split(cmd), input=prompt, capture_output=True, text=True,
                       timeout=180, cwd=str(ROOT))
    # Nonzero exit is always a failure, even if stdout is nonempty.
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "extractor failed").strip()
        raise ExtractorError(f"extractor failed (exit {r.returncode}): {err[:300]}")
    return validate_facts(_parse_facts_payload(r.stdout))


def extract_facts_ollama(title, body):
    """Optional local Ollama call, same shape as the historical implementation."""
    p = PROMPT.format(title=title, body=body)
    data = json.dumps({"model": MODEL, "prompt": p, "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=90)).get("response", "")
    except Exception as e:
        raise ExtractorError(f"ollama extractor failed: {e}") from e
    return validate_facts(_parse_facts_payload(resp))


ADAPTERS = {
    "cmd": extract_facts_cmd,
    "ollama": extract_facts_ollama,
}


def extract_facts(text, title=""):
    """Pluggable entry point: extract_facts(text) -> list[dict]. Raises ExtractorError."""
    name = resolve_extractor_name()
    if name not in ADAPTERS:
        raise ExtractorError(
            f"unknown MEMORY_EXTRACTOR={name!r}. "
            f"Choose one of: {', '.join(sorted(ADAPTERS))}. "
            f"Refusing silent downgrade."
        )
    body = text if len(text) <= MAX_BODY_CHARS else text[:MAX_BODY_CHARS]
    if len(text) > MAX_BODY_CHARS:
        print(f"note: body truncated to {MAX_BODY_CHARS} chars for extraction", file=sys.stderr)
    # Adapters already validate; re-validate as a single choke point.
    return validate_facts(ADAPTERS[name](title, body))


# Back-compat name used internally
def extract(title, body):
    return extract_facts(body, title=title)


def candidate_filename(note_stem, index, fact_payload):
    """Stable-but-unique candidate YAML name: stem prefix + index + content hash.

    Prevents two distinct notes that share the first 30 stem chars from overwriting
    each other's candidates.
    """
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", str(note_stem or "note"))[:30].strip("-") or "note"
    raw = f"{note_stem}\0{index}\0{fact_payload}\0{uuid.uuid4().hex}"
    h = hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"cap-{stem}-{index}-{h}.yaml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--observed", default=str(datetime.date.today()))
    args = ap.parse_args()
    # Validate registry shape before any candidate is written
    load_registry(force=True)
    CAND.mkdir(exist_ok=True)
    n = 0
    any_failed = False
    for fp in args.files:
        f = Path(fp)
        if not f.exists():
            print(f"skip missing: {f}", file=sys.stderr)
            any_failed = True
            continue
        # If reconcile already claimed this attempt (state=running, attempts bumped),
        # do NOT rewrite to pending, that would clear the claim marker and cause a
        # double-increment on the terminal failed/captured write.
        sp0 = state_path_for(f)
        prev0 = {}
        if sp0.exists():
            try:
                prev0 = json.loads(sp0.read_text()) or {}
            except Exception:
                prev0 = {}
        already_claimed = prev0.get("state") == "running"
        if not already_claimed:
            write_capture_state(f, "pending", facts=0, bump_attempts=False)
        try:
            # Redact BEFORE the note reaches any extractor model or command.
            safe_text, _hits = redact_secrets(f.read_text(errors="ignore"))
            safe_title, _ = redact_secrets(f.stem)
            facts = extract(safe_title, safe_text)
        except ExtractorError as e:
            write_capture_state(f, "failed", facts=0, error=str(e))
            print(f"capture failed for {f}: {e}", file=sys.stderr)
            any_failed = True
            continue
        except Exception as e:
            write_capture_state(f, "failed", facts=0, error=str(e))
            print(f"capture failed for {f}: {e}", file=sys.stderr)
            any_failed = True
            continue
        if not facts:
            write_capture_state(f, "failed", facts=0, error="zero_facts")
            print(f"capture zero facts for {f} (marked failed for reconcile)", file=sys.stderr)
            any_failed = True
            continue
        written = 0
        for i, x in enumerate(facts):
            if not isinstance(x, dict) or not x.get("fact"):
                continue
            fact_s, _ = redact_secrets(x.get("fact", ""))
            excerpt_s, _ = redact_secrets(x.get("excerpt", ""))
            scope = str(x.get("scope", "personal"))
            ftype = str(x.get("type", "project_fact"))
            target = target_note_for_scope(scope)
            # risk is not assessed here, left as "low"; safety relies on
            # policy.yaml red-lines + dual-agent judges in memory.py.
            rec = {
                "fact": fact_s,
                "type": ftype,
                "scope": scope,
                "source": {
                    "kind": "note",
                    "path": str(f),
                    "excerpt": excerpt_s,
                },
                "observed_at": args.observed,
                "target_note": target,
                "risk": "low",
            }
            # Serialize via safe_dump so model-derived fields (incl. type) are quoted
            # properly, never raw string interpolation into YAML.
            # Atomic publish: write candidates/.tmp-<id>.part (no *.yaml match),
            # full-write loop, then rename into place.
            body = yaml.safe_dump(rec, sort_keys=False, allow_unicode=True,
                                  default_flow_style=False)
            fname = candidate_filename(f.stem, i, fact_s)
            final = CAND / fname
            stem = Path(fname).stem
            tmp = CAND / f".tmp-{stem}-{uuid.uuid4().hex[:8]}.part"
            data = body.encode("utf-8")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(str(tmp), flags, 0o644)
            try:
                total = 0
                view = memoryview(data)
                while total < len(data):
                    written_n = os.write(fd, view[total:])
                    if written_n <= 0:
                        raise OSError(
                            f"short write publishing candidate: "
                            f"{total}/{len(data)} bytes"
                        )
                    total += written_n
            except Exception:
                os.close(fd)
                try:
                    os.unlink(str(tmp))
                except OSError:
                    pass
                raise
            else:
                os.close(fd)
            os.replace(str(tmp), str(final))
            n += 1
            written += 1
        if written == 0:
            write_capture_state(f, "failed", facts=0, error="no_valid_fact_dicts")
            print(f"capture produced no valid fact dicts for {f}", file=sys.stderr)
            any_failed = True
        else:
            write_capture_state(f, "captured", facts=written)
    print(f"captured {n} candidate fact(s) from {len(args.files)} note(s) -> {CAND}")
    if any_failed:
        sys.exit(1)


def _self_checks():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  ok  {name}")
        else:
            print(f" FAIL {name}" + (f": {detail}" if detail else ""))
            failures.append(name)

    check("personal target",
          target_note_for_scope("personal") == "03-resources/ai-memory/captured-personal.md")
    check("org target indexed",
          target_note_for_scope("org").startswith("03-resources/agent-systems/captured-"))
    check("project target stable",
          target_note_for_scope("project:northwind")
          == "03-resources/agent-systems/captured-project-northwind.md")
    check("same scope same file",
          target_note_for_scope("project:x") == target_note_for_scope("project:x"))
    # registry alias resolution (exact full-slug keys; proposed-merge disabled)
    check("registry alias personal identity",
          resolve_alias("personal") == "personal")
    check("registry proposed-merge disabled project-northwind",
          resolve_alias("project-northwind") == "project-northwind")
    check("registry no short-form hop client:northwind",
          resolve_alias("client:northwind") == "client-northwind")
    check("drop_patterns empty seed",
          fact_matches_drop_pattern("anything durable") is False)
    out, hits = redact_secrets("key s" "k-abcdefghij and a@b.co")
    check("redact api_key", "s" "k-abcdefghij" not in out and "[REDACTED:api_key]" in out)
    check("redact email", "a@b.co" not in out and "[REDACTED:email]" in out)
    check("schema inspectable", FACTS_JSON_SCHEMA["type"] == "array" and "items" in FACTS_JSON_SCHEMA)
    check("prompt inspectable", "JSON array" in PROMPT and "{title}" in PROMPT)
    check("adapters registered", set(ADAPTERS) >= {"cmd", "ollama"})

    # validate_facts
    good = [{
        "fact": "Uses weekly planning for research",
        "type": "workflow",
        "scope": "org",
        "excerpt": "We use weekly planning for research tasks daily.",
    }]
    try:
        v = validate_facts(good)
        check("validate_facts accepts good", len(v) == 1 and v[0]["type"] == "workflow")
    except ExtractorError as e:
        check("validate_facts accepts good", False, str(e))

    bad_type = [{**good[0], "type": "prediction"}]
    try:
        validate_facts(bad_type)
        check("validate_facts rejects bad type", False)
    except ExtractorError:
        check("validate_facts rejects bad type", True)

    bad_scope = [{**good[0], "scope": "evil"}]
    try:
        validate_facts(bad_scope)
        check("validate_facts rejects bad scope", False)
    except ExtractorError:
        check("validate_facts rejects bad scope", True)

    no_excerpt = [{**good[0], "excerpt": "  "}]
    try:
        validate_facts(no_excerpt)
        check("validate_facts rejects empty excerpt", False)
    except ExtractorError:
        check("validate_facts rejects empty excerpt", True)

    too_many = [dict(good[0]) for _ in range(MAX_FACTS_PER_NOTE + 1)]
    try:
        capped = validate_facts(too_many)
        check("validate_facts caps count", len(capped) == MAX_FACTS_PER_NOTE)
    except ExtractorError as e:
        check("validate_facts caps count", False, str(e))

    # filename collision avoidance
    a = candidate_filename("very-long-shared-prefix-note-alpha", 0, "fact A")
    b = candidate_filename("very-long-shared-prefix-note-beta", 0, "fact B")
    check("candidate names differ for distinct notes", a != b)
    check("candidate name has hash suffix",
          bool(re.match(r"cap-.+-\d+-[0-9a-f]{8}\.yaml$", a)))

    # yaml.safe_dump serializes type (no raw interpolation)
    dumped = yaml.safe_dump({"type": "workflow:special", "fact": "x: y"},
                            sort_keys=False, default_flow_style=False)
    loaded = yaml.safe_load(dumped)
    check("yaml safe_dump roundtrip type", loaded.get("type") == "workflow:special")

    # ExtractorError (not sys.exit) for unknown adapter, exercised via extract_facts
    # with env override would shell models; just check the exception type exists
    check("ExtractorError is Exception", issubclass(ExtractorError, Exception))

    # attempts: simulate reconcile claim (state=running) then finish without double bump
    with tempfile.TemporaryDirectory() as td:
        note = Path(td) / "n.md"
        note.write_text("hello\n")
        sp = state_path_for(note)
        sp.write_text(json.dumps({"state": "running", "attempts": 3, "facts": 0}) + "\n")
        # Monkeypatch resolve_extractor_name path by writing state directly
        write_capture_state(note, "failed", facts=0, error="test")
        st = json.loads(sp.read_text())
        check("no double-increment after reconcile claim", st.get("attempts") == 3)
        # Direct capture finish (pending → failed) should bump
        sp.write_text(json.dumps({"state": "pending", "attempts": 1, "facts": 0}) + "\n")
        write_capture_state(note, "failed", facts=0, error="test2")
        st2 = json.loads(sp.read_text())
        check("direct finish increments attempts", st2.get("attempts") == 2)

    # symlink-safe sidecar: a symlinked sidecar or symlinked parent is refused, target untouched
    with tempfile.TemporaryDirectory() as td:
        td = Path(td).resolve()
        victim = td / "victim.txt"
        victim.write_text("keep\n")
        note = td / "n.md"
        note.write_text("hello\n")
        os.symlink(victim, state_path_for(note))
        try:
            write_capture_state(note, "failed", facts=0, error="x")
            check("symlinked sidecar refused", False)
        except ValueError:
            check("symlinked sidecar refused", victim.read_text() == "keep\n")
        real_dir = td / "real"
        real_dir.mkdir()
        os.symlink(real_dir, td / "link")
        try:
            safe_io.assert_not_symlinked(td / "link" / "a.json", td)
            check("symlinked parent refused", False)
        except ValueError:
            check("symlinked parent refused", True)

    # the note is redacted BEFORE it reaches the extractor
    with tempfile.TemporaryDirectory() as td:
        td = Path(td).resolve()
        note = td / "n.md"
        note.write_text("Contact owner@example.com about the weekly backup job.\n")
        seen = []
        global extract, CAND
        old_extract, old_cand, old_argv = extract, CAND, sys.argv
        extract = lambda title, body: seen.append(body) or []
        CAND = td / "cands"
        sys.argv = ["capture.py", str(note)]
        try:
            try:
                main()
            except SystemExit:
                pass
        finally:
            extract, CAND, sys.argv = old_extract, old_cand, old_argv
        check("extractor never sees the raw secret", len(seen) == 1 and "owner@example.com" not in seen[0]
              and "[REDACTED:email]" in seen[0], str(seen))

    # policy-extension patterns redact BOTH the title (file stem) and the body
    with tempfile.TemporaryDirectory() as td:
        td = Path(td).resolve()
        pol = td / "policy.yaml"
        pol.write_text(yaml.safe_dump({"forbidden_patterns": [r"ACME-\d{4}"]}))
        note = td / "ACME-1234-notes.md"
        note.write_text("Ticket ACME-5678 says the weekly backup job runs on Sunday night.\n")
        seen = []
        old_extract, old_cand, old_argv = extract, CAND, sys.argv
        old_pol = os.environ.get("MEMORY_POLICY")
        os.environ["MEMORY_POLICY"] = str(pol)
        extract = lambda title, body: seen.append((title, body)) or []
        CAND = td / "cands"
        sys.argv = ["capture.py", str(note)]
        try:
            try:
                main()
            except SystemExit:
                pass
        finally:
            extract, CAND, sys.argv = old_extract, old_cand, old_argv
            if old_pol is None:
                os.environ.pop("MEMORY_POLICY", None)
            else:
                os.environ["MEMORY_POLICY"] = old_pol
        check("policy patterns redact title and body before the extractor",
              len(seen) == 1 and "ACME-" not in seen[0][0] + seen[0][1]
              and seen[0][0].count("[REDACTED") == 1 and "[REDACTED:secret]" in seen[0][1], str(seen))

    if failures:
        print(f"self-check FAILED: {len(failures)} case(s)")
        sys.exit(1)
    print("self-checks OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--self-check", "self-check"):
        _self_checks()
    else:
        main()
