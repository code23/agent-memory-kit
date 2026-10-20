# Agent memory kit

A reference kit for the way I give AI agents a shared, trusted memory. It is not a product.
It is the scripts, policy, templates and documents I use, cleaned up so you can read them,
borrow what helps and change the rest.

The reasoning is in the post: https://ansell.ai/blog/ai-agent-memory-layer/

## The method

**Staging versus trusted.** Agents write to a drafts area. They never write to the memory
they read. Staging is cheap and disposable. Trusted is small and checked.

**Promote, don't pour.** I do not dump documents into memory. A fact earns its place: one
explicit statement, a source I can re-read, an exact excerpt and a date. Reference material
stays where it is and gets linked.

**A second model checks every fact, and a third breaks ties.** One model marking its own
homework agrees with itself. A second model, ideally from a different provider, checks the
fact against the source. If the two disagree, a third decides. Deterministic gates run first:
known secret patterns, stale sources and high risk facts are parked for me before any judge
sees them, and notes are redacted before they go to the extractor. Those gates are regular
expressions, not magic. They will miss a secret in an unusual format, so treat every model
command you configure as something that can see your notes and excerpts, and extend the
patterns in your policy.

**Git on the memory.** Keep the vault in git. With `--commit` (or `MEMORY_GIT_COMMIT=1`)
each promotion is committed as `promote: <ledger id>`, so every change has history and an
undo. The default is off, so nothing is committed unless you ask. A wrong fact is one
`git revert` away.

**One memory every model reads.** Claude, Codex, Gemini, Cursor and local models all read the
same files. I do not keep a separate memory per tool.

**Search sits behind the files.** The files are the truth. Routing and search are derived
indexes I can delete and rebuild. Nothing lives only in a database.

**Start with one client, one page.** Do not build the system first. Write five facts for one
client, use them for a week, and add the funnel when proposing by hand becomes a chore.

## Folder map

```
README.md                  this file
LICENSE                    MIT
requirements.txt           PyYAML (and pytest, optional)
run-tests.sh               runs every test, offline
router/                    model free lexical router (build_index.py, route.py)
funnel/                    the promotion funnel
  memory.py                the consensus loop: gates, judges, promote, undo
  capture.py               extracts candidate facts from prose notes
  judges/judge.py          ready-made model command for any seat (API or a model's CLI)
  safe_io.py               the one symlink-safe file writer used by the funnel and the router
  policy.example.yaml      policy: types, scopes, secret patterns, judge roles
  registry.example.yaml    scope to destination map
  bin/                     thin wrappers and a cron script
  tests/                   offline tests
  TESTS.md                 what the tests cover
vault/                     example vault skeleton, scripts and templates
  scripts/                 vault_lint.py, vault_search.py
  templates/               note templates and the fact template
docs/                      the documents listed below
agent-instructions/        copy-ready snippets for CLAUDE.md, AGENTS.md, GEMINI.md, Cursor
examples/                  fictional facts, notes and demo scripts
```

## Documents

| Document | What it covers |
|----------|----------------|
| [docs/first-real-run.md](docs/first-real-run.md) | From a fresh clone to your first fact checked by real models, then a daily schedule |
| [docs/promotion-protocol.md](docs/promotion-protocol.md) | Inbox, evidence, write lock, local commit |
| [docs/folder-layout.md](docs/folder-layout.md) | An example vault with staging and trusted folders |
| [docs/how-agents-use-it.md](docs/how-agents-use-it.md) | The agent lifecycle: read, cite, propose, check. Includes a sequence diagram |
| [docs/judges.md](docs/judges.md) | Plugging in your own models and commands |
| [agent-instructions/](agent-instructions/README.md) | Snippets for CLAUDE.md, AGENTS.md, GEMINI.md and Cursor rules |
| [docs/team-setup.md](docs/team-setup.md) | One shared repo, who can promote, per client separation, leavers |
| [docs/maintenance.md](docs/maintenance.md) | Weekly lint, stale facts, undoing a fact, duplicates |
| [docs/faq.md](docs/faq.md) | Common questions, including how this compares with RAG and other tools |
| [funnel/TESTS.md](funnel/TESTS.md) | What the tests cover |
| [examples/](examples/) | Three fictional facts from Northwind Studio, plus demo scripts |

## Quick start

You need Python 3.9 or newer and PyYAML. I have tested it on Python 3.9, 3.12 and 3.14 on
macOS. It should run on Linux; Windows is untested.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

**Run the router on the examples.** It builds a small index and answers two questions, with
no model call:

```bash
examples/route-demo.sh
```

**Run the vault lint** on the skeleton vault, or point `VAULT_ROOT` at your own:

```bash
python3 vault/scripts/vault_lint.py
VAULT_ROOT=/path/to/your/vault python3 vault/scripts/vault_lint.py
```

**Run the tests.** They are offline and use fixtures:

```bash
./run-tests.sh
```

**Dry run the funnel with no model calls.** This copies the three example facts into a
temporary folder, runs the gates, and uses an offline stub in place of the judges. It
writes nothing outside the temporary folder:

```bash
examples/dry-run.sh
```

Dry runs are not model free in general. `memory.py run` without `--apply` still calls the
judge commands you configured, with your permissions, and `capture.py` still calls the
extractor. Only the stub in `examples/` makes no call. Point the variables at the stub until
you have read what your real commands do.

To use real models, set `MEMORY_JUDGE_A_CMD`, `MEMORY_JUDGE_B_CMD` and `MEMORY_TIEBREAK_CMD`
to commands that read a prompt on stdin and print JSON. The ready-made
`funnel/judges/judge.py` does this for Anthropic, OpenAI, Gemini, xAI, OpenRouter and local
OpenAI-compatible servers, or wraps a model's own CLI:

```bash
export MEMORY_JUDGE_A_CMD="python3 $PWD/funnel/judges/judge.py --provider anthropic --model <model>"
```

API keys come from your environment. Nothing in this kit stores one.

**Going from the demo to real use?** Follow [docs/first-real-run.md](docs/first-real-run.md),
and run `python3 funnel/memory.py doctor` at any point. It says in plain English what is set
up and what is missing (`doctor --ping` also sends each model a one-line test).

Paths are configurable: `MEMORY_ROOT` (funnel state), `VAULT_ROOT` (trusted vault, default
`./vault`), `STAGING_ROOT` (default `./staging`) and `MEMORY_POLICY`.

### Keep real data outside the clone

Treat this repository as code. For real use, set `MEMORY_ROOT` and `VAULT_ROOT` to a
private folder outside the clone (for example `~/memory-private/state` and
`~/memory-private/vault`), with its own git repository for the vault. The candidates,
ledger, archive, router index and capture sidecars (`*.capture-state.json`) then never sit
next to code you might publish. The `.gitignore` also excludes those runtime folders as a
second line of defence, but a private root is the safer habit.

## End-to-end walkthrough

This runs the whole loop on a throwaway folder with the offline stub, so you can see every
step with no keys and no network. Run it from the kit folder with the virtualenv active.

```bash
KIT="$PWD"
WORK="$(mktemp -d)"
export MEMORY_ROOT="$WORK/memory" VAULT_ROOT="$WORK/vault"

# 1. Judges. The stub makes no model call. Real commands would call a provider.
export MEMORY_JUDGE_A_CMD="python3 $KIT/examples/judge_stub.py"
export MEMORY_JUDGE_B_CMD="python3 $KIT/examples/judge_stub.py"
export MEMORY_TIEBREAK_CMD="python3 $KIT/examples/judge_stub.py"

# 2. Policy and registry live in the private root, not in the clone.
mkdir -p "$MEMORY_ROOT/candidates" "$VAULT_ROOT/03-resources/agent-systems"
cp funnel/policy.example.yaml "$MEMORY_ROOT/policy.yaml"
cp funnel/registry.example.yaml "$MEMORY_ROOT/registry.yaml"

# 3. An allowed destination: a scope maps to exactly one note in the vault.
python3 - <<'PY'
import os, yaml
p = os.environ["MEMORY_ROOT"] + "/registry.yaml"
r = yaml.safe_load(open(p))
r["aliases"]["client-harbour-bakery"] = "client-harbour-bakery"
r["destinations"]["client-harbour-bakery"] = "03-resources/agent-systems/captured-client-harbour-bakery.md"
open(p, "w").write(yaml.safe_dump(r, sort_keys=False))
PY
printf '# captured-client-harbour-bakery\n\n## Sources\n\n- example\n' \
  > "$VAULT_ROOT/03-resources/agent-systems/captured-client-harbour-bakery.md"
git -C "$VAULT_ROOT" init -q && git -C "$VAULT_ROOT" add -A && git -C "$VAULT_ROOT" commit -qm seed

# 4. Create a proposal. The example files hold placeholders for the paths and the date.
sed "s#__EXAMPLES__#$KIT/examples#; s#__TODAY__#$(date +%F)#" \
  examples/candidates/harbour-approval.yaml > "$MEMORY_ROOT/candidates/harbour-approval.yaml"

# 5. Dry run. Prints what would happen and writes nothing, but it DOES call the judge
#    commands above (a real judge would run with your permissions and send the excerpt).
python3 funnel/memory.py run

# 6. Apply. Promotes the fact, writes the ledger, and with --commit commits it to the vault.
python3 funnel/memory.py run --apply --commit
git -C "$VAULT_ROOT" log --oneline          # seed, then "promote: <ledger id>"

# 7. Review. A fact that fails a gate parks in review/. Make one by raising the risk.
sed "s#__EXAMPLES__#$KIT/examples#; s#__TODAY__#$(date +%F)#; s/risk: low/risk: medium/" \
  examples/candidates/harbour-status-report.yaml > "$MEMORY_ROOT/candidates/needs-review.yaml"
python3 funnel/memory.py run --apply
python3 funnel/memory.py list-review        # needs-review, with the reason it parked

# 8. Approval. A person decides. approve promotes it and rebuilds the router index.
python3 funnel/memory.py approve needs-review --commit
# (or: python3 funnel/memory.py reject needs-review --note "why")

# 9. Undo. Use the ledger id from the commit message. This removes the bullet from the note.
LID="$(git -C "$VAULT_ROOT" log -1 --format=%s | sed 's/promote: //')"
python3 funnel/memory.py undo "$LID"
git -C "$VAULT_ROOT" commit -qam "undo: $LID"   # undo does not commit; do it yourself

# 10. Rebuild the router index and ask it a question. approve and undo already rebuild it;
#     run is flagged dirty and rebuilt by this command, which is what cron calls.
python3 funnel/memory.py router-rebuild-if-dirty
python3 router/route.py --indexdir "$MEMORY_ROOT/router" --show \
  --allow-root "$VAULT_ROOT/03-resources" "who approves blog posts for the bakery"
```

`status` shows the lane counts at any point. Team routing (copying facts to a shared store)
is off unless you set `MEMORY_TEAM_ROUTING=1`; see [docs/team-setup.md](docs/team-setup.md).

## What this is not

- It is not a product, a service or a package. There is nothing to install or subscribe to.
- It is not a vector database or a RAG system. You can add search behind it.
- It is not a way to store everything. It is deliberately small.
- It is not a compliance programme. It helps you keep personal data out and gives you an
  audit trail, but you still need your own advice.
- It is not finished. It is the shape of what I use, with the personal parts removed.
  Expect to adapt the policy, the scopes and the judges.

## Licence

MIT. Copyright (c) 2026 Twenty & Three Ltd, trading as Code23. See [LICENSE](LICENSE).
