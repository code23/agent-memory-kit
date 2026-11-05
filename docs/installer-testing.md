# Mac installer acceptance

The installer is a release candidate. Passing the offline suite does not establish that a client can install it. Use fictional facts, an isolated installation root and two real Mac accounts for acceptance. Keep real client knowledge and personal memory out of the rehearsal.

## Checks and evidence

| Layer | Run | Required output |
| --- | --- | --- |
| Offline regressions | `PYTHON=python3.14 ./run-tests.sh` | Exit status, test counts, failures and source commit |
| Runtime packet | `node runtime/team-memory-verify.mjs` | Exact packet verification result |
| Independent review | Review the exact installer diff with a model family that did not write it | Findings, disposition and reviewed commit; no unresolved security findings |
| Native components | Actual macOS Keychain, PostgreSQL 18, Node 24 and bundled runtime | Each real check, any injected boundary, fixture cleanup and versions |
| Installed client | Follow [mac-setup.md](mac-setup.md) in the two actual account sessions | Observed results below, sanitized evidence and a release verdict |

The full offline suite requires Python 3.11 or newer and the packages in `requirements.txt`. It uses test doubles for external processes and credentials. Run targeted regression tests while correcting a defect, then the full suite once on the integrated candidate. Do not replace a failed native check with a mocked pass.

## Installed-client charter

1. Run `doctor` and `plan` before installation. Missing tools, invalid workspace, same account, writable software, unsafe permissions and occupied ports must fail before creating business state.
2. Install into a new owner-private root. Confirm that no existing database, personal memory, global model configuration or existing `log this` command changed.
3. Repeat the identical install. It must preserve the instance, credentials and database. Interrupt a first install and verify its documented recovery behaviour.
4. Start the service in the operator's logged-in session. Bind a project from the coding account through the documented secure credential transfer. Confirm the project contains credential references only.
5. Launch the actual chosen coding client through `memory-kit run`. Use the existing `log this` entry point to submit one fictional, sourced fact. Record the proposal ID; it must be pending and absent from reads.
6. In the protected operator context, read and approve the exact displayed revision and hash. Restart the service and use a fresh coding session to recall the published fact with its source.
7. Withdraw that fact and check every exposed read route. Revoke the token, remove membership and stop the service in separate cases; each must deny access or report unavailability without falling back to private memory.
8. From the actual coding UID, attempt access to the operator's root, database socket, credentials and process environment. Record actual denials. A simulated second UID does not qualify.
9. Make an ordinary unrelated project-instruction edit. Launch must still work; changing a managed workspace, URL, credential reference or instruction block must fail closed. Re-key explicitly and confirm the old token remains revoked.
10. Stop and start, including an exited but still-loaded job. Verify status agrees with the running service. A deliberate stop must persist across login. Check locked Keychain and logged-out operator behaviour.
11. Uninstall and verify business data and credentials remain. Reinstall the same candidate without reinitializing the database. A changed candidate must refuse until the protected upgrade procedure is supported.
12. Rehearse protected backup, quarantined restore and a fresh rebuild that reconciles current withdrawals and access. Do not activate an old archive or describe quarantine as recovered production service.

## Report contract

Save a dated report outside the public source checkout. Include:

- Exact source commit, operating system, architecture, Python, PostgreSQL, Node and coding-client versions.
- Scope and fixtures; say whether each check was offline, native component or installed-client evidence.
- One outcome per criterion: `PASS`, `FAIL`, `BLOCKED` or `NOT RUN`, with evidence and a reason where needed.
- Each defect's reproduction, correction, targeted check, actual retry and review disposition.
- A verdict of `PASS` only when every required installed-client criterion passes and required review is complete. An unavailable account, untested transfer or missing recovery path cannot produce a release pass.
- Fixture cleanup, retained data, services left running and the next required human action.

Keep passwords, tokens, raw credential errors, private paths and user/client identifiers out of public reports, logs and screenshots. Record successful secure-store acceptance without exposing its value. Native component evidence and the final visible QA report remain separate outputs.

## Current release gaps

The initial implementation has native component evidence, not a completed two-account installation. Secure transfer and coding-client use need live acceptance. Backup/current-authority recovery and upgrades are release gates. The existing public default installation remains in place until these are accepted.
