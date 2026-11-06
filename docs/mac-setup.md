# Mac setup — release candidate

The candidate installer provisions a business memory service on its owner's Mac. It creates a dedicated database and restricted roles, stores database credentials in macOS Keychain and binds a coding project to the local service. Complete two-account installation, secure transfer and recovery acceptance remain release gates. Use fictional information during testing; this is not a production installation approval.

## Prepare the Mac

| Requirement | Purpose |
| --- | --- |
| Apple Silicon Mac | First native test target; Intel is unverified |
| Separate operator and coding Mac accounts | Keep publication and database administration outside unrestricted coding agents' reach |
| Python 3.11 or newer | Run the installer using the standard library |
| Node.js 24 | Run the packaged service; no npm install is required |
| PostgreSQL 18 tools | Create and maintain the dedicated database |
| Git or a downloaded release checkout | Obtain the software |
| Your coding framework and authenticated model tools | Run coding sessions with their existing models |

Use a trusted operator account to maintain the software. Run unrestricted coding agents only in the separate coding account. A separate terminal, environment variable, Keychain label or container under one UID does not provide this boundary. Setup refuses the same account, root execution and software that the coding account can alter. It does not create Mac accounts or grant administrator permissions.

The coding account must be standard, without administrator/root group membership, custom sudo rules or another way to assume the operator's identity. Administrator accounts remain trusted. Software and data must live on a filesystem that enforces ownership; volumes configured to ignore ownership are refused.

The operator must remain logged in, with the required Keychain accessible, while the coding account uses the service. This is a user LaunchAgent, not a system daemon. Fast user switching and locked-Keychain behaviour need acceptance on the target Mac. A permanently logged-out operator is not a supported unattended arrangement.

Keep the existing three-model YOLO workflow. Storage, access checks and lexical reads do not make inference calls; the coding and review workflow retains its model requirements.

### Install prerequisites

If Homebrew is absent, follow its [official installation guide](https://docs.brew.sh/Installation). The formula route targets supported Apple Silicon systems. From the operator account:

```sh
brew install python@3.14 node@24 postgresql@18
export PATH="$(brew --prefix node@24)/bin:$(brew --prefix postgresql@18)/bin:$PATH"
python3.14 --version
node --version
psql --version
pg_dump --version
pg_restore --version
```

The [Python](https://formulae.brew.sh/formula/python@3.14), [Node](https://formulae.brew.sh/formula/node@24) and [PostgreSQL](https://formulae.brew.sh/formula/postgresql@18) formula pages document these install commands. Versioned Node/PostgreSQL formulas are keg-only, so the PATH step matters. Setup accepts explicit `--node` and `--pg-bin` locations, validates their resolved executables, and discovers a suitable Python without changing global PATH or shell files.

Do not run `brew services start postgresql@18` for this kit. Its database has separate storage and lifecycle. Homebrew may create a default cluster; the installer does not reuse it or repoint an existing database.

## Install as the operator

Obtain the reviewed candidate checkout and enter its root. The public default branch remains the previous file-vault kit until this candidate passes acceptance. Do not import a personal vault as an installation step.

These examples use the fictional workspace `demo-business` and an already-created standard Mac account `memory-coder`. Replace both deliberately. Workspace names contain 2–40 lowercase letters, digits or hyphens, starting with a letter; 32-character hexadecimal identifiers are refused.

```sh
node runtime/team-memory-verify.mjs
./memory-kit doctor --workspace demo-business --coding-user memory-coder
./memory-kit plan --workspace demo-business --coding-user memory-coder
./memory-kit install --workspace demo-business --coding-user memory-coder
```

`doctor` and `plan` are read-only. They check the account boundary, source/tool permissions, runtime versions, root and required listener availability. Resolve failures before installation. They never silently install dependencies or change an existing service.

`install` creates a dedicated PostgreSQL cluster, role credentials, the business workspace and a verified private software copy. Credentials are generated in memory and stored in Keychain; no manual SQL or password argument is required. Installation does not start the background service.

The default root is `~/Library/Application Support/Agent Memory Kit/demo-business`. It holds private configuration, database storage and versioned software outside the checkout. Do not share it with the coding account or publish it. If you choose a different `--root`, use that same root for all subsequent commands.

An identical reinstall preserves the instance, credentials and database. Changed software refuses in-place replacement until the protected upgrade procedure is supported. Incomplete database initialization needs operator recovery; do not delete database files to bypass an error.

### Start and inspect

```sh
./memory-kit start --root "$HOME/Library/Application Support/Agent Memory Kit/demo-business"
./memory-kit status --root "$HOME/Library/Application Support/Agent Memory Kit/demo-business"
```

The service exposes `http://127.0.0.1:47892/mcp`. PostgreSQL uses a Unix socket under the owner-private root, with no TCP database listener. Coding sessions receive only restricted memory API access.

`start` loads the owner LaunchAgent and enables start at login. A loaded job alone is not a healthy-service check. `status` distinguishes loaded service, running PostgreSQL and start-at-login configuration. `stop` drains the owned service/database and removes start-at-login configuration. Run `start` explicitly to enable it again; unrelated services must remain untouched.

After a Python package update, inspect `autostart_python_missing` in `status` and run `start` again if the recorded executable disappeared. If its configured Python selector is also gone and `start` refuses, run `stop`, then repeat the same candidate's `install` command under the available supported Python to refresh that selector. Then run `start` and confirm with `status`. An unknown PostgreSQL state is not reported as stopped: restore the required PostgreSQL 18 tools before attempting recovery.

## Bind the coding project

The agent receives a `read_submit` token. It can read published facts and propose pending facts, but cannot publish or obtain database credentials. From the operator terminal, first create a fictional business member:

```sh
./memory-kit operator --root "$HOME/Library/Application Support/Agent Memory Kit/demo-business" -- \
  members add --workspace demo-business --user coding-agent --role member
```

Token output must go directly through a secure input pipe to `memory-kit connect` in the coding account's own credential context. Never display it, put it in an argument, copy it to chat or save it in an ordinary file. `connect` reads stdin and stores the token in that account's Keychain; TTY input is refused.

The intended cross-account route is a pre-authorized SSH pipe into the coding account's active, unlocked session. Follow the [preflight, transfer and re-key commands](../agent-instructions/business-memory.md#credential-transfer-across-the-two-accounts). This requires separately prepared SSH access and verified host identity. Setup does not enable Remote Login, bypass authentication or assume `sudo` unlocks another user's Keychain. **The transfer has not passed two-account acceptance.** Do not improvise a file or terminal-display workaround. The final novice walkthrough remains a release gate until that exact route is tested.

The destination command has this shape; its stdin must be the secure token stream:

```sh
./memory-kit connect --project "$HOME/Projects/business" \
  --workspace demo-business --url http://127.0.0.1:47892/mcp \
  --instance demo-business-agent
```

Run it from the coding account with its own trusted checkout. It writes `.agent-memory.json`, managed project instructions and MCP entries in `.mcp.json` and `.codex/config.toml`. Configuration contains a Keychain reference and `${AGENT_MEMORY_TOKEN}`, never the token. Unrelated configuration is preserved; ambiguous or conflicting bindings are refused.

This unaccepted candidate currently requires a clean coding instruction context. Global Claude/Codex instruction files and alternate project instruction/rule paths are unsupported, as are existing `logthis`, `log this`, `log-this` or `log_this` capture routes. No reviewed-handoff override is implemented. Preserve those files and use a separate clean context for testing; do not delete an existing setup to make preflight pass. The [binding contract](../agent-instructions/business-memory.md) names the supported paths and recovery limits. This compatibility restriction is a release gate.

Business instructions reuse the existing `log this` intent. They do not install a competing capture command or a second memory store. Native model and authentication settings remain in place; this is not certification of every existing instruction setup.

Follow the existing tools' [search and verification guidance](../agent-instructions/business-memory.md#search-and-verify) for paraphrased questions and missing knowledge.

### Launch a coding session

From the coding account, launch the installed client through the profile:

```sh
./memory-kit run --profile "$HOME/Projects/business/.agent-memory.json" -- claude
# Or, when using Codex:
./memory-kit run --profile "$HOME/Projects/business/.agent-memory.json" -- codex
```

The wrapper validates the binding, retrieves only the agent token and passes it to that child. It does not change model routing. Restart the client after configuration changes. Claude Code and Codex configuration support does not certify cmux, T3, Grokbot or OpenBot; the chosen launch path needs live acceptance.

Unrelated edits to project instructions or other server settings should remain usable. Changes to managed memory configuration fail closed. Rotation requires revoking the old server token and explicitly reconnecting to a fresh Keychain instance. Do not overwrite secure-store entries or change workspace implicitly.

## Confirm the first fictional fact

Use the [installed-client acceptance charter](installer-testing.md).

1. Ask a business question in the coding session and verify the empty state.
2. Use the existing `log this` entry point to propose a sourced fictional fact. It must report “submitted for review” and remain absent from reads.
3. From the operator terminal, list proposals and review the returned proposal ID:

   ```sh
   ./memory-kit operator --root "$HOME/Library/Application Support/Agent Memory Kit/demo-business" -- \
     proposals list --workspace demo-business
   ./memory-kit operator --root "$HOME/Library/Application Support/Agent Memory Kit/demo-business" -- \
     proposals review --workspace demo-business --submission PROPOSAL_ID
   ```

4. Read the complete content and confirm the exact displayed hash in the protected terminal. Restart the service and recall the fact from a fresh coding session with its source.
5. Withdraw the knowledge, revoke the token and test outage separately. The client must respect each change and never fall back to personal memory.

The protected operator also has `knowledge list`, `knowledge revoke`, `tokens list`, `tokens revoke` and membership commands. These remain human administration actions. The coding account must not obtain that authority.

When you have finished testing, or before maintenance, stop the service:

```sh
./memory-kit stop --root "$HOME/Library/Application Support/Agent Memory Kit/demo-business"
```

## Uninstall, recovery and release

```sh
./memory-kit uninstall --root "$HOME/Library/Application Support/Agent Memory Kit/demo-business"
```

Uninstall stops owned services and removes verified software while preserving database, configuration and Keychain entries. Removing a checkout does not delete knowledge. The identical candidate can reinstall its software without reinitializing the database.

Protected backup, current-authority recovery and upgrades remain incomplete release gates. The bundled restore utility produces a quarantined offline archive. That is not an activated recovered service: an old snapshot may predate withdrawals, revoked access and review decisions. Do not activate it as a shortcut.

The [installation plan](mac-installation-plan.md) defines scope and [installer acceptance](installer-testing.md) defines the required output. Local runtime and native component checks do not replace a clean two-account client installation. The previous file-vault path remains the public default until all required checks and independent review pass.
