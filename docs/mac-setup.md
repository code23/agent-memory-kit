# Mac setup — release candidate

This is the first supported installation target being prepared: one business running its own memory service on a Mac. The runtime has passed a synthetic local rehearsal; a complete clean-Mac installation and the business `log this` binding have not yet passed acceptance. Do not use this guide as a production installation promise.

## What you need

| Requirement | Purpose |
| --- | --- |
| macOS, with an owner who can administer it | Run and maintain the local service |
| Node.js 24 | Run the tested memory artifacts; no npm packages are needed at runtime |
| PostgreSQL 18, including `psql`, `pg_dump` and `pg_restore` | Store business facts and operate backups |
| Git, or a downloaded copy of this repository | Obtain code, documentation and the runtime packet |
| Your coding framework and its authenticated model tools | Use the memory from coding sessions |
| A protected memory administration context | Keep database-owner and publication authority out of the coding agent's reach |

Keep the existing three-model YOLO workflow. The memory service does not replace that workflow or configure its models. Storage, token checks and lexical retrieval do not themselves make inference calls; that is different from the model requirements of the coding/review workflow around them.

For the Homebrew route, follow its [official installation guide](https://docs.brew.sh/Installation) first if `brew --version` is unavailable. Check the supported Mac/OS requirements there; the current supported package route targets Apple Silicon, while Intel requires separate verification.

Homebrew publishes [Node 24](https://formulae.brew.sh/formula/node@24) and [PostgreSQL 18](https://formulae.brew.sh/formula/postgresql@18):

```sh
brew install node@24 postgresql@18
export PATH="$(brew --prefix node@24)/bin:$(brew --prefix postgresql@18)/bin:$PATH"
node --version
psql --version
pg_dump --version
pg_restore --version
```

These versioned formulas are keg-only, so the PATH step matters. This installs PostgreSQL software and may create its default cluster; it does not prepare the protected memory database or its roles. Do not start or repoint an existing database as a shortcut. Commands were checked against the official formula documentation; installation on a clean Mac has not been rehearsed.

A missing prerequisite must be detected before memory setup writes business state. This candidate does not automatically install Homebrew, create Mac users, alter database permissions, add a background service or change an agent's global settings.

## Installation sequence

### 1. Choose the administration boundary

A separate terminal, Keychain label or Docker container is not an OS identity boundary. A coding agent with unrestricted shell access under the memory administrator's Mac account can reach that account's files and credentials. The installer must not claim otherwise.

For protected administration, use separate OS identities/access controls for the coding agent and memory administration. The exact first-client arrangement is a release decision, not something this draft silently configures. A single trusted-account setup has a different threat model and must be described as such before anyone chooses it.

### 2. Keep business data outside the checkout

The repository is software, not the business knowledge store. A protected operator prepares persistent PostgreSQL storage, backup custody and credentials outside the checkout. Do not put connection passwords, agent tokens, real notes or backup archives into this repository.

The source's previous file-vault kit remains available during this transition. Do not import a personal vault or silently move existing knowledge into PostgreSQL. Migration needs a separately reviewed, explicit source and destination.

### 3. Verify the runtime packet

From the repository root:

```sh
node runtime/team-memory-verify.mjs
```

The strict `runtime/` directory contains exactly five executable modules and their manifest. Keep documentation and license files outside it. The manifest detects changed/missing/extra files; it does not authenticate a malicious publisher or verifier. Read [SOURCE.md](../SOURCE.md) for provenance and reproduction.

### 4. Prepare PostgreSQL and bootstrap the business

The protected operator supplies an empty dedicated database, a database owner and separate existing reader, proposal-service and operator logins. Credentials come from the approved secure store, never command arguments, tracked files or chat.

The tested bootstrap command is:

```sh
node runtime/team-memory-bootstrap.mjs \
  --workspace demo-business --name "Demo business" --owner demo-owner \
  --reader-role memory_reader --submitter-role memory_submitter \
  --operator-role memory_operator
```

`DATABASE_URL` must be supplied to this process through the protected bootstrap credential context. Replace the synthetic business/owner identifiers deliberately. Do not run a second PostgreSQL server against an existing data directory.

**Unfinished installation work:** this repository does not yet provide a guided Mac routine that provisions these roles and securely connects all three host contexts. The command above is a verified component, not a complete novice installation command.

### 5. Start the restricted service

From the proposal-service credential context:

```sh
node runtime/team-memory-server.mjs --allow-submissions
```

It binds to `127.0.0.1:47892`. The coding agent never receives the database connection. Its separate personal token permits published reads and, when granted, pending proposals. It cannot review or publish through the memory API.

### 6. Connect the coding agent and the existing `log this` command

The local MCP endpoint is:

```text
http://127.0.0.1:47892/mcp
```

A protected operator creates a `read_submit` token and transfers it directly to the coding user's secure store. Connection configuration contains a credential reference, never the raw token. The chosen business/workspace must be explicit; setup must refuse a missing or incomplete binding instead of falling back to another business.

The client binding must preserve the existing `log this` entry point:

1. The active coding agent drafts a small, sourced business fact.
2. `memory_submit` records a pending proposal and returns its ID.
3. Protected review displays and approves the exact revision/hash.
4. A fresh coding session uses `memory_context` to retrieve the published fact.

Report “submitted for review” until publication succeeds. Never fall back to a personal staging folder. The binding and exact client configuration are still being prepared; native Claude Code MCP rehearsal is not certification of cmux, T3, Codex or automatic hooks.

### 7. Check the first fact before using real information

Use a fictional business fact first. Confirm that it is absent before review, present in a fresh session after review/restart, and absent after withdrawal. Remove the test agent's access and confirm subsequent requests are denied. Confirm that the coding account cannot obtain bootstrap/operator credentials.

A natural-question local rehearsal passed 32 structured checks, with an additional 227 integrated checks and 63 existing client-routing tests. Those are internal evidence, not a clean-machine installation pass.

## Backup, recovery and updates

A tested quarantined archive is not an activated recovered service. Production recovery/current-authority reconciliation remains a release gate. Do not restore an old snapshot, revive its tokens and restart as a shortcut: it may predate withdrawals, membership changes or review decisions.

The installation guide still needs an accepted protected backup/restore procedure, start-at-login and restart behavior, safe upgrade/rollback steps, and an uninstall that preserves business data by default. No installer may delete knowledge merely because its software checkout is removed.

## Release gate

Before making this the default public client installation path, complete and rehearse the Mac setup, secure credential/identity boundary, existing-command binding, chosen coding-client configuration and recovery procedure. The three-model YOLO workflow remains intact. Automatic Drive/Dropbox ingestion and a before/after answer-quality benchmark are separate later work.
