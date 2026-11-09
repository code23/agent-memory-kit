# Mac installer acceptance

## Current disposition

See the authoritative [NO GO disposition and readiness table](mac-installation-plan.md#current-disposition--no-go-for-protected-client-rollout).
Candidate repository checks pass with **178 installer tests** (baseline **143 PASS**) in native Darwin user-temp fixtures; this does not establish guard readiness.
The preference-omission, project-identity and qualified directory-ABA witnesses now refuse. Five regressions in `tests/test_installer_context.py` (`test_review_refuses_managed_preferences_added_after_planning`, `test_review_refuses_project_replacement_after_fourth_plan_check`, `test_review_refuses_skill_directory_aba_after_remembered_presence`, `test_review_credentials_presence_uses_planned_metadata`, `test_review_project_identity_stays_paired_after_final_plan_check`) failed on the previous source and pass now. They use fictional fixtures with native identity/UID/custody/TTY mocked; the ABA test keeps its controlled restoration and parent-mtime assumptions.
The optional guard remains parked; accepted historical core and the existing pilot are unchanged, and pilot health was not checked.

### Offline fixture environment for future verification

Use the OS-provided **native Darwin user temporary directory** for ephemeral
fixtures, not the archive directory and not generic `/private/tmp`. For example,
resolve it with `getconf DARWIN_USER_TEMP_DIR`, pass that value as `TMPDIR` only to
the test process, and use the already-prepared Python environment. Keep retained
stdout/results in the external archive evidence location. Standard ephemeral
fixtures auto-clean; do not chmod ancestors or weaken guards.

The verification controls were: representative short-fixture 3 PASS on baseline and
candidate; full generic-short runs of 143/173 tests with 0 FAIL / 1 ERROR each; the remaining
`AGENT_WRITABLE_SOFTWARE` correctly reflected a world-writable temporary ancestor.
Native Darwin user-temp cleared that case in both one-test controls, then baseline
143 PASS and candidate whole-repository ALL PASSED including 173 installer tests. None
of these controls changed source, modes or guards. The earlier archive 36 failures
are now exactly attributed by IDs/exceptions/call chains, not inferred from counts.
The original ABA witness was a bounded fictional public-export experiment; it is
now the regression test named above. Run the context tests on their own with
`TMPDIR="$(getconf DARWIN_USER_TEMP_DIR)" python3 -m unittest discover -s tests -p 'test_installer_context.py'`.



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
9. Make an ordinary project-instruction edit. Launch must refuse until fresh context approval; changing a managed workspace, URL, credential reference or instruction block must fail closed. Re-key explicitly and confirm the old token remains revoked.
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

## Launch-context candidate qualification

The narrower local-observation contract is approved. The invented-client attempt
remains stopped; the implemented fixture exercises the real
`claude-code/2.1.318` contract with explicit native identity/source-root/UID/custody
mocks. The fixed remote/native-time exclusions appear in both packet and approval:
remote policy fetch, runtime MCP instructions, hook output, auto-update and remote
plugin marketplaces. Local files are inventoried or cause conservative refusal.

`tests/test_installer_context.py` exercises canonical terminal review/re-hash,
read-only preflight, initial/bound connect, two actual controlled Python children,
rotation, changed-context denial before credential/write/spawn effects and
packet-free revoke. It also checks unknown arguments/environment/imports/plugins,
missing/malformed/stale/stripped authority, binary and selector drift, project
replacement, absent-source additions, parent/symlink/inode replacement and a
separate process holding a shared launch lock during bounded revoke publication.
Auth values are absent from packets and retained by the child. Structured capture
directives and original personal/default sources are checked; native LLM meaning
is not inferred from wording or regex.

Existing binding unit tests retain their functional/security assertions with an
explicit approval-boundary mock and updated Popen assertions. Their legacy Codex
commands do not qualify Codex for production admission. The argv comparison
checks argument values rather than Python list object identity because the
protected launcher constructs a checked argv list.

The final offline suite ran once: 153 installer tests, 11 failures and 27 errors.
The earlier archive-guard baseline was 9 failures and 27 errors. The two new
failures were CLI unit fixtures: preflight omitted the newly forwarded
`native_argv`/`review_context` expectations, and reconnect did not explicitly mock
approval before credential stdin. They were new failures, not baseline failures.
The fixtures now provide explicit native argv and reconnect approval. One added
CLI denial test asserts that denied authority prevents stdin-buffer reads,
Keychain construction, writes and child creation through actual `main()`.

Only those three CLI tests were rerun after correction: all three passed. The
153-test/full suite was not rerun. The remaining 36 archive-guard failures/errors
remain qualified and blocked; no guard was relaxed, host permission changed or
scratch relocated. There is no global green result. The prior 10 context and 68
client passes remain separate local synthetic evidence.

Whole-candidate Claude code-review attempts timed out without verdicts. Subsequent
scoped native Claude Opus 5.5 reviews of observer, authority and lifecycle returned
changes needed. The later targeted privacy/revoke repair does not replace those
findings or approve the prototype; its independent scoped review remains lead-owned.
Actual native loading, LLM meaning, real two-UID/Keychain custody and host setup
remain unrun. The earlier CLI fixture correction changed no runtime source. See the
[subset and limits](mac-installation-plan.md#local-observer-candidate-and-limits).

## Targeted privacy and revoke repair qualification

**Privacy remains blocked.** The final disposition below supersedes any general
privacy conclusion drawn from the passing scoped fixtures in this section.

Two focused regressions first failed on the actual prototype: unrelated project
memory was enumerated, and revoke reported certainty after a separate process
released its shared launch lock during publication. One shared correction replaced
the traversal with a fixed typed inactive-root entry and moved bounded exclusive
lock acquisition before publication. An additional targeted policy regression
found that an ancestor false setting could substitute for missing selected-user
policy; the tighter subset now requires explicit false in the selected user's
native `settings.json` and rejects contrary settings. All failures and corrections
are retained as evidence rather than renamed baseline failures.

The final focused context suite passed 15 tests. The guarded real-child workflow
also passed with fictional foreign-memory markers present: read/enumeration
instrumentation fails on any foreign-root access, and neither marker nor project
name/path enters the packet/registry. Malformed inactive enums/types/paths,
re-enabled/missing policy, uncontended lock ownership across publication and
sticky uncertainty in the exact release-at-publication race are covered. Native
identity, roots, UID, custody and terminal confirmation remain explicit mocks.
No whole-suite, legacy binding or CLI rerun was needed for this scoped repair;
the historical results above remain qualified, not a global pass.

Read-only bytecode investigation produced a harmless cached-module sentry with
`-I -B`: the cached body executed while source and installer hash were unchanged.
It establishes an open pre-import trust-boundary issue, not a repaired software
custody boundary or an actual two-UID exploit. No launcher/host/security changes
were made. Future verification must prove a cache sentry cannot execute before
checks, reject unknown/writable descendants and symlink/ACL/volume changes, and
retain the controlled-child workflow. A late `authority()` check alone is not
that verification. Other scoped-review findings remain open; see the
[partial repair limits](mac-installation-plan.md#targeted-privacy-and-revoke-corrections-prototype-still-held).

### Scoped review closure follow-up

The metadata-only privacy approach failed independent review because the generic
project walk could reach a custom native config inside a valid project. A new
canonical namespace admission now refuses overlap and linked/aliased configuration
ancestors before context intake. Regressions exercise the actual public project
validator and foreign poison instruction files. Guards cover `os.scandir` (used
by `os.walk`), `os.listdir`, `os.open` with tracked relative directory descriptors,
`Path.iterdir` and the source reader. Terminal approval mocks remain intact.

A separate RED covered missing/unsafe launch locks and an actual flock `ENOLCK`
error. Revoke now publishes `approval: null` and generation+1 with uncertainty;
repairing the lock still leaves launch denied. Approval refuses without publishing,
and publication errors propagate. Independent native Claude Opus 5.5 reviews
passed the revoke-certainty correction and the acquisition-error hardening only.
The broader prototype remains unapproved.

Final focused suite: 19 PASS, preserving both complete actual controlled Python
child workflows and the process-lock race tests. An initial fixture-only failure
came from test snapshot enumeration crossing its own new guard after production
admission had denied; direct write/credential/spawn assertions corrected that
fixture. No guard was disabled. The most recent lead full run before this delta
was 159 installer tests, 9 failures and 27 errors, qualified archive-guard results.
The prior 153/11FAIL/27ERROR run remains historical, including its two corrected
CLI fixture failures. No full-suite rerun or global green is claimed here. Native,
meaning, two-UID/Keychain, loader and broader local coverage gates remain open.

### Final disposition

The 19 passing focused tests exclude a subsequently demonstrated failing alias
fixture: an external native configuration's `projects` link points into the
coding project, whose walk attempts the foreign instruction read before rejecting
the link. This additional fixture used fictional data and intercepted the read.
The privacy approach is stopped; do not report its invariant as passed.

The bytecode probe proves that unlisted cached bytes can execute in a writable
fixture without changing the source hash. The fresh software copier excludes
caches, so this is not a demonstrated exploit of a fresh protected installation.
Source-only loading has a feasible independent design disposition; implementation,
provisioning and real two-account verification remain open.

### Read-order redesign qualification

Baseline alias/read-order regressions failed before the planner: a private cache
symlink into a valid project reached foreign poison instructions, and a late
ancestor skill alias was rejected only after a body read. The new observer admits
all fixed roots first, discovers metadata slots, then materializes them. Tests
retain actual public project validation and real read/list/open guards; profile
and managed binding slots are included. Absent-slot additions and metadata drift
at the phase boundary refuse before materialization. A first planner run revealed
an inactive-root metadata open crossing the guard; parent-anchored inspection
corrected it without weakening the guard. The guarded actual controlled-child
approve/connect/rotate/revoke workflow passed afterwards.

Legacy binding fixtures explicitly mock the new early metadata admission together
with their existing approval boundary; they do not certify native discovery.
Accepted revoke implementation remains byte-identical. No full-kit rerun or
native/host acceptance is inferred: previous 159 tests with9FAIL/27ERROR and
153 with11FAIL/27ERROR qualifications remain. Design review was NO VERDICT;
independent code review remains required before approval.

The read-order candidate preserves accepted revoke and existing read/classifier
function bytes. Controlled-child and targeted alias checks passed before the
implementation stop; full-kit and independent code review remain lead-owned.

### Shared planned IO correction (held for independent review)

Independent review and a fictional witness showed a regular private directory
could replace an admitted source between the plan check and body read. Current
inode checks alone were insufficient. The new shared ContextVar scope supplements
existing checks: every opened directory must match its planned identity before
listing/yield, and each file must match its planned parent/name and leaf metadata
before body reads. Both observer reads and binding snapshots use this boundary.
It resets in finally/nested scopes, and is absent during effectful binding writes.
Discovery listings use one descriptor-anchored scandir helper, retaining the open
parent while consuming names/stat. No Path.iterdir listing remains in the observer.

Whole-plan checks run at phase boundaries; per-read checks cover their own chain
and leaf. A deterministic several-dozen-directory count regression guards against
quadratic whole-plan scans. When an ancestor `.claude` is the selected global
config, its already-classified global slots/categories apply without treating
history/projects as unknown project-local sources. A real fictional HOME-ancestor
fixture exercises the unmocked scope algorithm and privacy guard.

The exact body-move witness first failed, then denied before foreign bytes. Final
focused context tests:29PASS, including two actual controlled Python-child
lifecycles, directory/listing and binding snapshot moves, public-run early ordering,
ContextVar reset, aliases and drift. Legacy binding tests:68PASS with explicit
boundary mocks. Accepted operator/revoke/registry helpers and other non-owned
files remain byte-identical; existing read safety checks are supplemented, not
removed. No whole-context/native/host readiness follows. Independent Claude code
review is required. Latest lead full run167tests9FAIL27ERROR lacks failure IDs,
so identical-baseline attribution is unproved. Node24 cannot load libsimdjson;
lead reported Node22v22.16.0 integrity PASS. Neither runtime nor host repair was
run here. Loader/token/rollback/broader coverage and real native/twoUID/Keychain
acceptance remain open.
