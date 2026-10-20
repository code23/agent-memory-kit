# Judges, extractors and other pluggable commands

The funnel never hard codes a model or a provider. Every model call goes through a
command that you configure with an environment variable. The command reads a prompt on
standard input and prints the reply on standard output. That is the whole contract.

| Role | Environment variable | What it does |
|------|----------------------|--------------|
| `judge_a` | `MEMORY_JUDGE_A_CMD` | First reviewer of each candidate fact |
| `judge_b` | `MEMORY_JUDGE_B_CMD` | Second reviewer, ideally a different model or provider |
| `tiebreak` | `MEMORY_TIEBREAK_CMD` | Third reviewer, used only when the first two disagree, and always for boundary facts |
| extractor | `MEMORY_EXTRACTOR_CMD` | Pulls candidate facts out of a prose note (`capture.py`) |

Optional hooks:

| Variable | Purpose |
|----------|---------|
| `MEMORY_CAPACITY_CMD` | A command that prints `status=ok remaining_percent=<n>`. If set, weekly work only runs above a 5 percent reserve. Unset means no gate. |
| `MEMORY_TEAM_BIN` | Absolute path to a command with `search` and `submit` subcommands, used to copy eligible facts into a shared team store. It is never discovered on `PATH`. Team routing is off unless `MEMORY_TEAM_ROUTING=1`, and only scopes in the registry's `team_share_scopes` are shared. |
| `MEMORY_GIT_COMMIT` | Set to `1` (or pass `--commit` to `run` and `approve`) to commit each promoted note to the vault's git repo as `promote: <ledger id>`. Off by default. |
| `MEMORY_ARCHIVE_ROOT`, `MEMORY_ARCHIVE_MOUNT` | Where expired deadlocks are archived, and an optional mount point that must be present. |
| `MEMORY_ROOT`, `VAULT_ROOT`, `MEMORY_POLICY`, `STAGING_ROOT` | Where state, the trusted vault, the policy file and staging live. |

## Reply shape

For one item the judge prints `{"verdict": "promote" | "reject" | "hold", "reason": "..."}`.
For a batch the prompt lists items as `=== ITEM <kind> id=<id> ===` and the judge prints a
JSON list of `{"id", "verdict", "reason"}`. Anything that does not parse is recorded as
`invalid`, and an invalid vote on a required judge parks the fact as a deadlock. It never
counts as a vote either way.

## Example provider block

`funnel/policy.example.yaml` lists the three roles and an example provider block. Model
names are placeholders. Keys are read from the environment by your own command:

```yaml
judges:
  judge_a:  {cmd_env: MEMORY_JUDGE_A_CMD}
  judge_b:  {cmd_env: MEMORY_JUDGE_B_CMD}
  tiebreak: {cmd_env: MEMORY_TIEBREAK_CMD}
providers_example:
  provider_one: {api_key_env: PROVIDER_ONE_API_KEY, model: example-model-small}
```

## The ready-made command: `funnel/judges/judge.py`

You don't have to write a judge. `funnel/judges/judge.py` reads the prompt on stdin, asks
one model and prints only the first JSON object or list in its reply, however much else the
model says. If the model fails, times out or returns no JSON, it exits non-zero, which the
funnel counts as an invalid vote (so the fact waits for a person). Standard library only.

| Provider | Command | Key variable |
|---|---|---|
| Anthropic | `judge.py --provider anthropic --model <model>` | `ANTHROPIC_API_KEY` |
| OpenAI | `judge.py --provider openai --model <model>` | `OPENAI_API_KEY` |
| Google Gemini | `judge.py --provider gemini --model <model>` | `GEMINI_API_KEY` |
| xAI | `judge.py --provider xai --model <model>` | `XAI_API_KEY` |
| OpenRouter | `judge.py --provider openrouter --model <vendor/model>` | `OPENROUTER_API_KEY` |
| Any OpenAI-compatible server (Ollama, LM Studio, vLLM, Mistral) | `judge.py --provider openai-compatible --base-url <url> --model <model>` | `--key-env NAME` if it needs one |
| A model's own CLI | `judge.py --exec "claude -p"` | the CLI's own sign-in |

Options: `--key-env` reads the key from a different variable, `--timeout` (default 100
seconds; the funnel gives each seat 120), `--max-tokens` (default 2048). The same command
works as `MEMORY_EXTRACTOR_CMD`.

`python3 funnel/memory.py doctor` checks every seat: command found, key present (never
shown), the same command or provider in two seats. `doctor --ping` sends each seat a one-line
test prompt and flags any that don't answer with clean JSON.

## Writing your own

A judge command is any program that reads stdin, calls your provider with a key from
`os.environ`, and prints the JSON reply. `examples/judge_stub.py` shows the shape and
makes no call, which is what the dry run uses.

Use a different provider for each role where you can. Two copies of the same model agree
with each other for the wrong reasons.
