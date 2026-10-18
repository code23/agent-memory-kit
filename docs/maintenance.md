# Maintenance

Memory rots if nobody looks after it. These jobs take about fifteen minutes a week.

## Weekly lint

Run the lint across the vault and read the output:

```bash
VAULT_ROOT=/path/to/trusted python3 vault/scripts/vault_lint.py
```

It checks the folder scaffold, Markdown links, wikilinks, duplicate note names and notes
without headings or sources. Fix errors the same day. Warnings can wait, but do not let
them pile up.

Then rebuild the router index and look at the weak summary list it writes. A weak summary
is a note that will be hard to find:

```bash
python3 router/build_index.py --src "$VAULT_ROOT/03-resources/agent-systems" --out "$ROUTER_INDEX"
cat "$ROUTER_INDEX/router-lint.md"
```

Also look at the funnel's own state:

```bash
python3 funnel/memory.py status
python3 funnel/memory.py list-review
```

Anything parked for review needs a decision. A review folder that grows every week means
the policy is too strict or the proposals are poor. Fix one or the other.

## Stale fact review

Every fact has an observed date. Once a month, sort a page by date and read the oldest
facts. For each one ask: is it still true, and could I still point to its source?

- Still true: leave it. Optionally re-confirm by proposing it again with a new source date.
- No longer true: remove it with a commit (see below).
- Cannot tell: mark it with a short note in staging and check with the person who knows.

Pages for finished clients and ended projects can be moved to an archive folder. Moving
them out of the indexed folders stops agents reading them.

## Undoing a bad fact with git

When commits are enabled (`--commit` or `MEMORY_GIT_COMMIT=1`), every promotion is one
commit named `promote: <ledger id>`, so every promotion has one undo.

1. Find it:

   ```bash
   git -C "$VAULT_ROOT" log --oneline --grep "^promote:"
   git -C "$VAULT_ROOT" log -S"part of the wrong fact" --oneline
   ```

2. Look at what it changed: `git -C "$VAULT_ROOT" show <commit>`.
3. Undo it: `git -C "$VAULT_ROOT" revert <commit>`. The revert is itself a commit, so
   the history shows the fact, the removal and when.
4. If the funnel promoted it, also record the decision so the same proposal does not return:
   `python3 funnel/memory.py undo <ledger id>`, or reject the proposal.
5. Rebuild the router index.

Do not rewrite history as routine. A revert is the record that it happened. The one exception
is erasing personal data or a secret, which needs a history purge (see the FAQ on erasure).

## Consolidating duplicates

Duplicates creep in as the same fact stated three ways.

1. Search for the topic with `vault/scripts/vault_search.py` and with the router.
2. Pick the clearest wording and the best source. Keep that one.
3. Remove the others with a single commit whose message names the kept fact.
4. If two facts conflict, do not average them. Find which source is newer or more
   authoritative, keep that one, and note the superseded fact in the commit message.
5. The funnel already refuses exact duplicates of a fact that is on its target page, so
   most duplicates come from reworded facts. Short, one idea facts make this easier.

## Housekeeping

- Delete old files in `funnel/done/` and `funnel/rejected/` only after your retention
  period. Back them up first if they matter for audit.
- Back up the memory repository like any other repository. It is plain files and history.
- Review the policy file once a quarter: allowed types, scopes, deny lists and judges.
