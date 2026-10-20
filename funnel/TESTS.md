# Funnel tests

Everything here is offline. Judges, extractors and the team-memory CLI are mocked or
replaced by fixtures, and each test works in a temporary tree. Nothing reads or writes
live memory. Run them all from the kit root with `./run-tests.sh`, or one at a time:

```bash
python3 funnel/memory.py self-check
python3 funnel/capture.py --self-check
python3 funnel/tests/integration_phase0.py
python3 funnel/tests/test_batched_judges.py
python3 funnel/tests/test_deadlock_policy.py
python3 funnel/tests/test_retriage_batches.py
python3 funnel/tests/test_exact_duplicate_gate.py
python3 funnel/tests/test_private_team_boundary.py
python3 funnel/tests/test_quoted_judgment.py
python3 funnel/tests/test_triage_cron.py
python3 funnel/tests/test_router.py
python3 funnel/tests/test_judge_adapter.py
python3 funnel/tests/test_doctor.py
```

`pytest funnel/tests` also collects the unittest based suites.

## What is covered

| Area | File | Cases |
|------|------|--------|
| Safe target paths | `memory.py` | relative `.md` under the vault is accepted; absolute, `..`, `~` and non-Markdown paths are rejected |
| Safe append | `memory.py` | a directory swapped for a symlink between check and write is refused |
| Secret redaction | `memory.py`, `capture.py` | emails and API key shapes become `[REDACTED:kind]`; clean text is unchanged |
| Source verification | `memory.py` | `verified`, `changed`, `missing`, `unreadable`; fail closed, so missing is never verified |
| Review envelopes | `memory.py` | round trip, reason codes, judge verdicts, hashes |
| Scope registry | `memory.py`, `capture.py` | aliases, destinations, unknown scopes park |
| Judge verdicts | `memory.py` | strict JSON parsing; promote, reject, hold, invalid |
| Consensus | `memory.py` | every pair and tiebreak combination; invalid means deadlock; boundary facts need three promotes |
| Pluggable judge commands | `test_batched_judges.py` | command split, prompt on stdin, unset command or bad output becomes invalid |
| Batched judging | `test_batched_judges.py` | batch ids, untrusted data markers, fallback to single items, same outcome as unbatched |
| Sensitivity tags | `memory.py` | tags are recorded and notify, but never park by themselves |
| Team routing | `test_batched_judges.py`, `test_private_team_boundary.py` | off by default, positive scope allowlist, explicit absolute `MEMORY_TEAM_BIN`, deny lists, duplicate checks, private marker |
| Redaction before models | `capture.py`, `test_batched_judges.py` | the extractor receives redacted title and body, including patterns added in the active policy; target-note text with a secret is withheld from judge prompts |
| Symlink-safe writes | `capture.py`, `test_batched_judges.py`, `test_router.py` | symlinked sidecars (capture and reconcile), notify-pending, ledger file or directory, and router index output are refused and nothing is written through them |
| Promotion commits | `test_batched_judges.py` | `MEMORY_GIT_COMMIT=1` makes one `promote: <ledger id>` commit in a temp git repo; a non-git vault does not break promotion |
| Deadlock policy | `test_deadlock_policy.py` | weekly retry, expiry, archive, capacity gate, recovery |
| Re-triage | `test_retriage_batches.py` | dry run, apply, evidence changes mid run |
| Exact duplicate gate | `test_exact_duplicate_gate.py` | normalised duplicate detection against the target note |
| Quoted judgement | `test_quoted_judgment.py` | a quoted opinion is not accepted as an agent opinion marker |
| Cron wrapper | `test_triage_cron.py` | empty queue, triage failure, weekly failure exit codes, candidates under a private `MEMORY_ROOT`, including one written with `~` |
| Router | `test_router.py` | ranking, ambiguity, scope limited reads, malformed index handling |
| Judge command | `test_judge_adapter.py` | strict replies: bare JSON or one code fence accepted; prose, several objects or a quoted vote refused; request shape per provider (key in a header, never the URL); missing key fails before any call; HTTP and network errors never show the response body; `--exec` mode |
| Doctor | `test_doctor.py` | missing seats, folders and vault named in plain English; missing key named but never shown; same provider in two seats; the offline stub next to a real model fails; a wrapped CLI's arguments are never shown; `--ping` flags a seat without clean JSON |
| Integration | `integration_phase0.py` | end to end promote, reject, park and undo in a temporary tree |

## Rules for new tests

- Never call a real model. Replace entries in `memory._JUDGE_FNS` or mock `subprocess.run`.
- Never point a test at a real vault. Use a temporary directory and set `MEMORY_ROOT` and `VAULT_ROOT`.
- Do not run `memory.py run --apply` against live data from a working copy unless you
  intend to. Dry run is the default.
