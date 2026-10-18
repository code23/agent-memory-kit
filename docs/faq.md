# FAQ

Each answer stands on its own, so you can jump straight to the question you have.

## 1. Is Google Drive, SharePoint or Notion with AI a memory layer?

No. They are storage and reference. They hold documents, and an AI feature on top can search
or summarise them. A memory layer is a small, reviewed set of facts that agents are told to
trust, each with a source and a date. Your drive can be the source a fact points at. It
should not be what the agent reads as truth, because it holds drafts, old versions and
opinions next to the facts.

## 2. How is a memory layer different from RAG or a vector database?

RAG retrieves chunks of whatever you indexed, ranked by similarity. A memory layer decides
what is worth keeping before anything is retrieved. The two combine well: the memory layer
is the curated set, and search sits behind the files if you want it. This kit routes with
plain lexical ranking over titles and summaries, so there is no embedding store to run. If
your corpus outgrows that, add a vector index over the same Markdown files. The files stay
the source of truth.

## 3. Does it work with Claude, ChatGPT or Codex, Gemini, Cursor and local models?

Yes, because the memory is files and a few commands. Any agent that can read a file and run
a command can use the router. The snippets in `agent-instructions/` cover `CLAUDE.md`,
`AGENTS.md`, `GEMINI.md` and Cursor rules. For judging, each role is a command you point at
whichever model or local runtime you like, so mixing providers is a configuration change.

## 4. Do I need a database?

No. The trusted memory is Markdown in a git repository. The funnel keeps its working state
as small YAML and JSON files in folders. The router index is a generated text file that you
can delete and rebuild. Git gives you history and undo. If you later add search, it is a
derived index, not a new source of truth.

## 5. How big should it get?

Smaller than you expect. Aim for pages an agent can read in one go, with one clear summary
line each. A few hundred reviewed facts across your clients and ways of working is a lot of
value. If a page becomes hard to read, split it. If facts are rarely used, archive them.
Growth is a warning sign, not a goal.

## 6. What goes in, and what stays as reference?

Promote, don't pour. In goes a short, explicit, durable statement with a source: a
preference, a decision, a rule, a boundary or a tool fact. Stays as reference: documents,
transcripts, specs, long emails, meeting recordings and anything that changes daily. Link to
the reference from the fact's source. If an agent needs the full document it can open it.
It does not need it pasted into memory.

## 7. Can I run it without any model calls?

Yes, in two ways. The deterministic parts (path safety, source checks, secret checks, scope
checks, duplicate checks, lint, routing and search) never call a model. And the dry run in
`examples/dry-run.sh` uses an offline stub in place of the judges, so you can watch a
proposal travel through the funnel with no keys and no network. A fully manual version is
also valid: a person writes the fact and commits it.

## 8. What about GDPR and client data?

The design helps, but it does not make you compliant on its own. Keep personal data out of
memory: the checks match emails, phone numbers and money figures with regular expressions,
and the instructions tell agents never to propose personal data or transcripts. Those
patterns are a safety net, not a guarantee, and they will miss personal data in formats
they do not know. Store how you work with a client, not the client's records. Keep one
scope per client so access can be limited. Check where your judge and extractor models
process data, because redacted notes, facts, excerpts and target-note text are sent to them.

Erasure needs more than a revert. `git revert` or `memory.py undo` removes the content from
the current files, but git history, every clone and every backup still hold it, and so do
the ledger, the review and done folders and any model provider logs. To erase a fact for
real: remove it from the working files, purge it from history with `git filter-repo`
(which rewrites every commit that touched it; force-push if you have a remote), delete or
rewrite the ledger and candidate files that quote it, and then deal with every other clone
and every backup, which keep the old history until they are replaced or purged too. Plan
for that before you promote anything personal, and take advice for your own situation.

## 9. How is this different from Claude or ChatGPT built-in memory?

Built-in memory belongs to one vendor, one account and one assistant. You usually cannot
see every item, review it against a source, put it in version control, or share it with a
different tool. This approach is the opposite: one memory every model reads, owned by you,
reviewed before it is trusted, with a history. You can still use built-in memory for
personal convenience. Treat it as a separate thing from the team's trusted record.

## 10. How does this compare with Mem0, Supermemory or Basic Memory?

These are different points on a spectrum, and I would check each project's current
documentation before deciding. As I understand them, hosted or API based memory services
focus on automatically extracting and retrieving memories at runtime, often with embeddings
and a managed store. Basic Memory keeps Markdown notes that an assistant can read and write
through a tool. This kit is smaller and more opinionated about review: nothing becomes
trusted without a source and a second model's check, with an optional commit, and the output is plain files
in git. If you want automatic recall with little process, a service may suit you better.
If you want an audit trail and human control, this is closer. They can also work together.

## 11. What does the second model check cost?

Each fact is judged by a short prompt containing the fact, its type and scope, and the
source excerpt, so it is small. The funnel batches several facts into one call and only
calls the third model when the first two disagree. The deterministic gates reject most bad
proposals before any model is involved. Your cost depends on your provider and volume, so
run the dry run, count the calls it would make, and multiply. For a team proposing a few
facts a day the cost is usually small next to the time it saves.

## 12. How do I start?

One client, one page. Pick a client you work with often. Create a single page for them.
Write down five facts you wish every agent knew, each with a source and a date. Commit
the page, point your agent instructions at it, and use it for a week. Add the funnel only
when proposing facts by hand becomes a chore.

## 13. Why a second and third model rather than one?

One model checking its own claim tends to agree with itself. A second model, ideally from a
different provider, checks the fact against the source independently. If the two disagree,
a third breaks the tie. Disagreement is useful information: it usually means the fact is
vague or the source does not quite say it. Facts that cannot get agreement stay parked for a
person.

## 14. What happens when a fact is wrong?

Revert it. If you run with commits enabled (`--commit` or `MEMORY_GIT_COMMIT=1`), each
promotion is one commit named `promote: <ledger id>`, so `git revert` removes exactly that
fact and the history records what happened and when. Without commits, use
`memory.py undo <ledger id>` and commit the result yourself. Then ask why it got through: a weak source, a vague
fact, or a policy gap. Fix that, so the same kind of error is caught next time.
See `docs/maintenance.md`.

## 15. Is this a product?

No. It is a reference kit: scripts, a policy file, templates and documents showing one
way of doing it. Read it, copy what is useful, change the rest.
