"""Private-brain-only marker blocks team routing (synthetic, no vault data).
Run: python3 -B tests/test_private_team_boundary.py"""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("memory", str(Path(__file__).resolve().parents[1] / "memory.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.load_registry = lambda *a, **k: {"aliases": {}, "destinations": {}, "team_share_scopes": ["org", "client:northwind", "project:atlas"], "team_exclude": []}
base = {"type": "decision", "fact": "synthetic"}
n = 0
def check(c, scope, exp):
    global n
    n += 1
    assert bool(m.team_route_eligible(c, scope)) == exp, (c, scope, exp)

for scope in ("org", "client:northwind", "project:atlas"):
    check(dict(base), scope, True)                                   # unmarked business allowed
    check({**base, "private_brain_only": True}, scope, False)        # top-level marker
    check({**base, "review": {"private_brain_only": True}}, scope, False)  # review marker
    for v in ("yes", 1, ["x"], {"a": 1}):
        check({**base, "private_brain_only": v}, scope, False)      # truthy non-boolean
        check({**base, "review": {"private_brain_only": v}}, scope, False)
    for v in (False, None, 0, ""):
        check({**base, "private_brain_only": v}, scope, True)       # falsy allowed
        check({**base, "review": {"private_brain_only": v}}, scope, True)
    for rv in ("junk", ["private_brain_only"], 5, None, {}):
        check({**base, "review": rv}, scope, True)                   # malformed review safe
        check({**base, "review": rv, "private_brain_only": True}, scope, False)  # top-level still honoured
for c in (dict(base), {**base, "private_brain_only": True}, {**base, "review": {"private_brain_only": False}}):
    check(c, "personal", False)
# Envelope persistence: a review-marked candidate keeps the marker through rebuild.
def build(c):
    return m.build_review_envelope("deadlock", "synthetic", candidate=c)
def repark(c):
    return m.attach_review_envelope(c, build(c))
marked = {**base, "scope": "org", "review": {"private_brain_only": True, "reason_code": "old"}}
env1 = build(marked)
n += 1; assert env1.get("private_brain_only") is True, "envelope lost review private marker"
once = repark(marked); twice = repark(once); thrice = repark(twice)
for r in (once, twice, thrice):
    n += 1; assert r["review"].get("private_brain_only") is True
    for scope in ("org", "client:northwind", "project:atlas"):
        check(r, scope, False)                                       # still denied after repark
top = {**base, "scope": "org", "private_brain_only": True}
n += 1; assert build(top).get("private_brain_only") is True
check(repark(repark(top)), "org", False)
for c in (dict(base), {**base, "review": {"private_brain_only": False}},
          {**base, "private_brain_only": 0}, {**base, "review": "junk"}, {**base, "review": None}):
    n += 1; assert "private_brain_only" not in build(c), c           # no extra flag
    check(repark(c), "org", True)
n += 1; assert "private_brain_only" not in m.build_review_envelope("deadlock", "x")  # no candidate
n += 1; assert build(marked)["candidate_sha256"] == build({k: v for k, v in marked.items() if k != "review"})["candidate_sha256"]
n += 1; assert build(marked)["candidate_sha256"] == build({**marked, "review": {"x": 1}})["candidate_sha256"]
# Exact-hash private opt-out (synthetic payloads only).
REG = {"aliases": {}, "destinations": {}, "team_share_scopes": ["org", "client:northwind", "project:atlas"], "team_exclude": []}
def with_hashes(h):
    m.load_registry = lambda *a, **k: {**REG, **({} if h is None else {"private_candidate_hashes": h})}
priv = {**base, "fact": "synthetic-alpha-fact"}
other = {**base, "fact": "synthetic-beta-fact"}
ph = m.candidate_sha256(priv)
for hs in (None, [], [m.candidate_sha256(other)]):
    with_hashes(hs)
    for scope in ("org", "client:northwind", "project:atlas"):
        check(priv, scope, True)                                     # empty/missing/different hash: unchanged
with_hashes([ph.upper()])
for scope in ("org", "client:northwind", "project:atlas"):
    check(priv, scope, False)                                        # exact hash denied (case-insensitive)
    check(other, scope, True)                                        # different payload unaffected
    check({**priv, "review": {"votes": 3, "age": 9, "reason_code": "x"}}, scope, False)  # review changes keep opt-out
    check({**priv, "review": {"private_brain_only": False}}, scope, False)
    check(repark(priv), scope, False)                                # persists across reparks
    check({**priv, "fact": "synthetic-alpha-fact edited"}, scope, True)  # payload change = different hash
n += 1; assert m.candidate_sha256(priv) == m.candidate_sha256({**priv, "review": {"x": 1}}) == ph
check(priv, "personal", False); check(other, "personal", False)
with_hashes([ph])
check({**priv, "private_brain_only": True}, "org", False)         # marker guard still applies
check({**priv, "sensitivity": "x"}, "org", False)
# Real registry loader parses the key (temp file, no live config).
import tempfile, os
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "r.yaml"); open(f, "w").write("private_candidate_hashes:\n  - " + "AB" * 32 + "\n")
    n += 1; assert spec.loader and importlib.util.module_from_spec(spec)
    mm = importlib.util.module_from_spec(spec); spec.loader.exec_module(mm)
    n += 1; assert mm.load_registry(f)["private_candidate_hashes"] == ["ab" * 32]
    open(f, "w").write("aliases: {}\n")
    n += 1; assert mm.load_registry(f)["private_candidate_hashes"] == []
# Malformed private_candidate_hashes shapes are fatal before any candidate (synthetic).
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "r.yaml"); good = "ab" * 32
    def load(txt):
        open(f, "w").write(txt); return mm.load_registry(f)
    for ok_txt, exp in (("private_candidate_hashes: []\n", []), ("private_candidate_hashes:\n  - '" + good.upper() + "'\n", [good]),
                        ("private_candidate_hashes:\n  - ' " + good + " '\n", [good]), ("x: 1\n", [])):
        n += 1; assert load(ok_txt)["private_candidate_hashes"] == exp
    bad = ["scalar: " + good, "bool: true", "zero: 0", "null: null", "map: {a: b}", "short: [abc123]", "wild: ['*']",
           "nonstr: [1]", "nested: [[x]]", "nonhex: ['" + "g" * 64 + "']", "long: ['" + good + "0']"]
    for b in bad:
        key, val = b.split(": ", 1)
        txt = "private_candidate_hashes: " + val + "\n"
        n += 1
        try: load(txt)
        except mm.RegistryConfigError: pass
        else: raise AssertionError(("accepted malformed", txt))
print("private team boundary tests OK", n)
