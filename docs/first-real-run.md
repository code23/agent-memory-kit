# Your first real run

From a fresh clone to your first fact checked by real models and promoted into your own
memory. Allow about an hour. Do the dry run in the README first if you want to see the
whole loop without any keys.

You need:

- Python 3.9 or newer, and git.
- Three models from **different companies**, one for each seat (Judge A, Judge B and the
  tiebreak). Either API keys or command-line tools you already sign in to.
- A first client you work with often, and one fact about them you can point to a source for.

## 1. Install

```bash
git clone https://github.com/code23/agent-memory-kit.git
cd agent-memory-kit
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
KIT="$PWD"
```

## 2. Make private folders for the real data

The clone is code. Your memory lives somewhere else, so it can never be published by
accident.

```bash
export MEMORY_ROOT=~/memory-private/state
export VAULT_ROOT=~/memory-private/vault
mkdir -p "$MEMORY_ROOT/candidates" "$VAULT_ROOT/03-resources/agent-systems"
cp funnel/policy.example.yaml "$MEMORY_ROOT/policy.yaml"
cp funnel/registry.example.yaml "$MEMORY_ROOT/registry.yaml"
git -C "$VAULT_ROOT" init -q
export MEMORY_GIT_COMMIT=1   # every promotion becomes one commit, so every fact has an undo
```

Put the `export` lines in your shell profile once you are happy with them.

## 3. Choose the three models

Each seat is a command. The kit includes one that works with most providers:
`funnel/judges/judge.py`. It reads the prompt, asks the model and prints only the JSON
the funnel needs, however chatty the model is.

**The one rule: a different company in each seat.** Two models from the same company tend
to agree with each other for the wrong reasons.

### Option A: API keys

| Provider | Seat command | Key variable |
|---|---|---|
| Anthropic (Claude) | `python3 $KIT/funnel/judges/judge.py --provider anthropic --model <model>` | `ANTHROPIC_API_KEY` |
| OpenAI (GPT) | `python3 $KIT/funnel/judges/judge.py --provider openai --model <model>` | `OPENAI_API_KEY` |
| Google (Gemini) | `python3 $KIT/funnel/judges/judge.py --provider gemini --model <model>` | `GEMINI_API_KEY` |
| xAI (Grok) | `python3 $KIT/funnel/judges/judge.py --provider xai --model <model>` | `XAI_API_KEY` |
| OpenRouter (many) | `python3 $KIT/funnel/judges/judge.py --provider openrouter --model <vendor/model>` | `OPENROUTER_API_KEY` |
| Local (Ollama, LM Studio, vLLM) | `python3 $KIT/funnel/judges/judge.py --provider openai-compatible --base-url http://localhost:11434/v1 --model <model>` | none |

Use the exact model name from your provider's model list. Model names change every few
months, so the kit doesn't guess one for you.

Keys come from your environment, never from a file in the kit. Load them from your secret
store when the shell starts. On a Mac, for example, after saving a key in Keychain:

```bash
export ANTHROPIC_API_KEY="$(security find-generic-password -s anthropic-api -w)"
```

Then fill the seats (this example mixes three companies):

```bash
export MEMORY_JUDGE_A_CMD="python3 $KIT/funnel/judges/judge.py --provider anthropic --model <claude model>"
export MEMORY_JUDGE_B_CMD="python3 $KIT/funnel/judges/judge.py --provider gemini --model <gemini model>"
export MEMORY_TIEBREAK_CMD="python3 $KIT/funnel/judges/judge.py --provider openai --model <openai model>"
```

### Option B: command-line tools you already use

If you'd rather use a subscription than API keys, wrap the tool's own CLI. It must accept
the prompt on standard input and answer without asking you anything:

```bash
export MEMORY_JUDGE_A_CMD="python3 $KIT/funnel/judges/judge.py --exec 'claude -p'"
```

Check your tool's documentation for its non-interactive mode, and run it once by hand to
make sure it doesn't stop for a login or a permission prompt. `judge.py` strips everything
except the JSON.

### Where your data goes

Each judge sees the proposed fact, its exact quote from the source and the note it would
land on. That text goes to the provider you chose. Pick providers and regions you'd be
happy to send client material to, and check your contracts. A local model keeps it on
your machine.

## 4. Check the set-up

```bash
python3 funnel/memory.py doctor
```

It lists what is ready and, in plain English, what is missing and how to fix it. When it
says ready, send each model a one-line test:

```bash
python3 funnel/memory.py doctor --ping
```

That makes one small call per seat. A seat that answers with anything other than clean
JSON is flagged here, before it can confuse a real vote.

## 5. Add your first client

Each client gets a scope and exactly one page, so a fact about one client can never land on
another's page. Edit `$MEMORY_ROOT/registry.yaml`:

```yaml
aliases:
  client-acme: client-acme
destinations:
  client-acme: 03-resources/agent-systems/captured-client-acme.md
```

Then create the page:

```bash
printf '# Acme\n\n## Sources\n\n- kickoff notes\n' \
  > "$VAULT_ROOT/03-resources/agent-systems/captured-client-acme.md"
git -C "$VAULT_ROOT" add -A && git -C "$VAULT_ROOT" commit -qm "Acme page"
```

## 6. Propose your first fact

A proposal is one small file in `$MEMORY_ROOT/candidates/`. Copy the shape from
`vault/templates/candidate-fact.yaml` or `examples/candidates/`:

```yaml
fact: At Acme, every homepage change is signed off by the marketing director.
type: workflow
scope: client:acme
source:
  kind: note
  path: /path/to/your/kickoff-notes.md
  excerpt: every homepage change is signed off by the marketing director
observed_at: 2026-10-20
target_note: 03-resources/agent-systems/captured-client-acme.md
risk: low
```

The excerpt must appear in the source **word for word**, and it must be at least four
words. Opinions ("I think"), contact details and money figures are refused on purpose.

## 7. Run it

```bash
python3 funnel/memory.py run            # dry run: shows each vote, writes nothing
python3 funnel/memory.py run --apply    # promotes, commits and logs
git -C "$VAULT_ROOT" log --oneline      # "promote: <ledger id>"
```

If a fact parks for review, `python3 funnel/memory.py list-review` says why. Approve it with
`approve <id> --commit` or reject it with `reject <id> --note "why"`.

## 8. Point your agents at it

Copy the snippet for each tool from [`agent-instructions/`](../agent-instructions/README.md)
into its instruction file (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md` or Cursor rules) and fill in
the four paths. From then on each agent reads the memory first and proposes new facts to
`$MEMORY_ROOT/candidates/` instead of writing to the trusted notes.

## 9. Run it on a schedule

`funnel/bin/triage-cron` checks the inbox, runs the funnel when there is something to
check, rebuilds the search index and logs to `$MEMORY_ROOT/ledger/triage-cron.log`. It
costs nothing when the inbox is empty.

A scheduler doesn't load your shell profile, so give it a small wrapper that sets the
variables and reads the keys from your secret store at run time:

```bash
#!/bin/bash
# ~/memory-private/run-triage.sh  (chmod 700)
. /path/to/agent-memory-kit/.venv/bin/activate   # the Python that has PyYAML
export MEMORY_ROOT=~/memory-private/state VAULT_ROOT=~/memory-private/vault MEMORY_GIT_COMMIT=1
export ANTHROPIC_API_KEY="$(security find-generic-password -s anthropic-api -w)"
# ...the other keys, and the three MEMORY_*_CMD lines from step 3...
exec /path/to/agent-memory-kit/funnel/bin/triage-cron
```

Then run it daily, or hourly if you want new facts the same day:

```bash
crontab -e
0 7 * * * $HOME/memory-private/run-triage.sh
```

If reading keys from your secret store fails when cron runs it, use your system's user
scheduler instead (launchd on a Mac, a systemd user timer on Linux).

## What to expect in the first fortnight

- **More reviews than promotions.** The gates are strict on purpose. Read why each fact
  parked and adjust the policy (scopes, allowed types, source age) or write better
  proposals. A review pile that keeps growing means one of those needs fixing.
- **Some ties.** Disagreement between two models usually means the fact is vague or the
  source doesn't quite say it. Tighten the wording rather than overruling it.
- **Fifteen minutes a week.** See [maintenance.md](maintenance.md) for the weekly lint,
  stale-fact review and undo.

When it's running, the [team set-up](team-setup.md) covers sharing one memory across
several people.
