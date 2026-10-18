# Promotion protocol

This is how a fact gets from "something an agent noticed" to "something every agent will
read". The rule is simple: nothing reaches the trusted memory without evidence and a lock, and
(when you enable it) a commit. Promote, don't pour.

## The two areas

- **Staging.** A drafts area. Agents and people can write here freely. Nothing in staging is
  trusted and nothing in staging is read as fact.
- **Trusted.** The memory every agent reads. Only the promotion step writes here.

## The steps

1. **Inbox.** An agent, a person or the capture script proposes a fact by writing one
   proposal file into the inbox (the `candidates/` folder, or an inbox folder in a shared
   repo). A proposal is a single explicit statement in the fact template format: the fact, a
   type, a scope, a source path, an exact excerpt from that source, an observed date, a
   target note and a risk level.
2. **Evidence check.** Before any model sees the proposal, deterministic checks run. The
   source must exist, the excerpt must appear in it word for word, the source must be recent
   enough, the scope must be known, the type must be allowed, the risk must be low, and the
   text must not contain secrets, contact details or money figures. Opinions and guesses
   ("I think", "probably") are refused. Anything that fails goes to review, not forward.
3. **Second opinion.** Two reviewers judge the proposal against the source. Each returns
   promote, reject or hold. Two promotes means promote. Two rejects means reject. Any
   disagreement goes to a third reviewer who breaks the tie. Boundary facts (things about
   what must never happen) need three promotes.
4. **Write lock.** Promotion takes an exclusive lock on the memory so two writers cannot
   interleave. A stale lock is detected and recovered.
5. **Write and commit.** The fact is appended to its target note with its provenance (source,
   date, ledger id) and a ledger line is written. If you turn commits on, the same step
   commits the note to the vault's git repository:

   ```
   promote: <ledger id>
   ```

   Commits are opt-in: pass `--commit` to `memory.py run` or `memory.py approve`, or set
   `MEMORY_GIT_COMMIT=1`. Without it the funnel writes the file and the ledger and you commit
   yourself. If the vault is not a git repository the funnel warns and carries on. The commit
   is local. The vault repository has no remote unless you add one deliberately.
6. **Notify and undo.** Anything sensitive, boundary or tie broken is added to a notify
   feed so a person can look afterwards. Every promotion has a ledger entry, and
   `memory.py undo <ledger id>` or `git revert <commit>` removes it. `undo` edits the note but
   does not commit, so commit the removal yourself.

## Who may promote

Any tool may promote an eligible proposal, as long as it leaves evidence, holds the lock and
makes the commit (when commits are enabled). There is no special "approved" model. What matters is the evidence and
the history. A person reviews the commits, not every fact.

## What always goes to a person

Hard stops are never decided by a model: secrets, an unverifiable or stale source, high risk,
unknown scope, and two reviewers who cannot agree after a tiebreak. These park the proposal
with a reason code until someone approves or rejects it.

## What is deliberately not here

No automatic push to a remote, no promotion of unreviewed text, no promotion from a source
that cannot be re-read, and no bulk import. Reference material stays where it is and is
linked, not copied.
