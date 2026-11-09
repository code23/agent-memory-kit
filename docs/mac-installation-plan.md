# First Mac client release

## Current disposition — NO GO for protected client rollout

**NO GO:** keep the optional launch-context guard as a draft, parked
pending native acceptance. Accepted historical core evidence and the existing
internal pilot are unchanged; live pilot health was not rechecked. Original
programme start of 5 November at 13:20 is retained; the previously recorded
product repair count was 16, before this bounded whole-candidate repair slice.

**2.1.319 observer candidate, 9 November.** The explicit local observer contracts
are `claude-code/2.1.318` and `claude-code/2.1.319`. This adds a candidate, not
native acceptance. The protected rollout remains **NO GO** and the version-matched
native guarded-lifecycle rehearsal gate is unchanged. See the
[qualification and limits](#local-observer-candidate-and-limits).

See [whole-candidate repair and remaining findings](#whole-candidate-repair-9-november-2026-offline).

**Observation hardening, 8 November (offline only).** The three confirmed
observation defects below are now closed in `memory_kit/context_authority.py` by
one shared correction: presence and identity come from the planned metadata
that `_remember_metadata`/`_check_plan` already maintain, never from a fresh
unplanned stat. Managed-preference paths and the excluded credentials entry are
recorded in the plan; tree, empty-source, project `.claude` and `.codex`
collectors use remembered presence; a planned directory that disappears during
listing refuses; the export's project device/inode come from the plan, and the
plan is rechecked after the last body read. Five fictional regressions failed on
the previous source and pass now (three witnesses, plus two from independent
review: credentials presence, and identity staying paired after the final
check). Context tests **34 PASS**, including the controlled-child
approval/connect/reconnect/drift-denial/revocation workflow; the original
witness script now refuses; repository checks **exit 0, ALL PASSED**, including
**178 installer tests**, in native Darwin user-temp. Independent Claude review:
**ACCEPT WITH LOW FINDINGS**; two accepted findings fixed. The third (a vanished
tree root raises a bare `FileNotFoundError`, still fail-closed) is retained.
Other fresh-stat refusal checks (`.git`/worktree, signed remote cache metadata,
ancestor binding) were not changed. Implementation: Codex `gpt-6.1-sol`; Claude did not
author product code. No native client, host,
two-UID or Keychain step ran.

Before the hardening above, fresh native Darwin user-temp fixtures resolved the
earlier environmental test negatives: baseline **143 PASS**; candidate repository
checks **exit 0, ALL PASSED**, including **173 installer tests**. Exact original archive-run failure IDs,
exceptions and call chains now match between baseline and candidate: 28 socket-path
length, 4 ownership-disabled-volume and 4 unsafe-ancestor cases. Earlier matching
counts alone were insufficient; the new row-level comparison supplies the evidence.
These historical environmental negatives remain recorded, not current product
failures. Passing offline checks do not establish guard readiness.

Three independent discovery contracts completed with **CHANGES_REQUIRED**. Their
responses each repeat the same three finding identities with shortened wording;
they represent nine claims, not eighteen. Source adjudication confirms three defects, including the qualified ABA witness
below. The other six claims remain unconfirmed or conservative refusals and are
not promoted to demonstrated defects. The earlier Gemini `planned-source-io/v1` **PASS_FOR_SCOPE**
remains conditional on the stated, unshown discovery contract. Its exact native
ID was explicitly selected, but returned output lacks a server-model field. Accepted revoke
and registry bytes are unchanged. Neither scoped pass approves the whole guard.
These findings concern consistency and source coverage within the ongoing
observation; the approved guarantee still excludes later edits and native
consumption, without claiming an immutable filesystem snapshot or universal confinement.

The three cases, as confirmed before the hardening (each now refuses offline):

- **Adversarial FAIL — preference omission:** an unsupported preference created
  after planning is still advertised absent in the returned export. A fresh
  observation denies. This confirms that preference path, not every signature or
  git-path variant whose parent metadata may already be watched.
- **Adversarial FAIL — project identity misbinding:** replacing the project after
  the fourth/final plan check returns old instruction content stamped with the
  replacement directory's inode. This is an observed export/binding defect, not
  a demonstrated native-client or host exploit.
- **Qualified adversarial FAIL — collector ABA:** a fictional full-public-export
  witness moves a remembered skill directory away and restores it plus the
  parent's mtime before later checks. Export returns an absent directory slot
  and omits its existing source. Ordinary moves may be caught; this result depends
  on the stated controlled ABA/metadata-restoration interleaving.

Fresh Node 24 v24.22.2 version and packaged integrity checks pass. Earlier missing
Homebrew-library failures are historical; recovery occurred outside this task,
with no host action here. Earlier Node 22 v22.16.0 integrity PASS does not meet the
installer's required major 24. Default Claude Code 2.1.319 now has an explicit
observer candidate: native guarded-lifecycle acceptance remains unqualified.

Local test
passes and witnesses use fictional inputs; native identity/UID/custody/TTY mocks
remain labelled. Source-only pre-import loading, broader coverage, token/rollback,
real native capture meaning/loading, two-UID/Keychain custody, protected bootstrap,
host acceptance and product release remain open. Historical backend/global checks
were not rerun. Dated and narrower outcomes below remain historical evidence;
this section is the authoritative current go/no-go disposition.

| Component | Evidence | Status | Remaining gate |
| --- | --- | --- | --- |
| Historical core | Council-reviewed bootstrap, restricted service, pending proposals, terminal review, persistence/recall and quarantined restore; later native core capture/recall rehearsal | Historical internal acceptance | Does not accept optional guard or client rollout |
| Fresh offline checks | Baseline 143 PASS; candidate repository exit 0 / ALL PASSED, including 178 installer tests after hardening | PASS in native-temp fixture environment | Native gates remain |
| Shared planned IO | Gemini planned-source-io/v1 conditional scoped PASS; 29 context / 68 mocked-boundary binding passes | Conditional/local evidence | Assumed discovery contract is not accepted |
| Discovery | Preference omission, project identity and qualified collector ABA witnesses now refuse; 5 regressions RED then GREEN; Claude review ACCEPT WITH LOW FINDINGS | Fixed offline (fictional fixtures, native identity mocked) | Native guarded lifecycle; unchanged fresh-stat refusal checks remain unqualified |
| Revoke/registry | Prior scoped Claude PASS; accepted bytes unchanged | Scoped acceptance retained | Not whole-guard acceptance |
| Node 24 | Fresh v24.22.2 and packaged integrity PASS | Required runtime available | No host/install acceptance inferred |
| Current client | Default 2.1.319; explicit contract 2.1.319, with 2.1.318 compatibility | 2.1.319 observer candidate; no native acceptance | Version-matched actual guarded lifecycle |
| Host/two-UID/Keychain | No new native acceptance | OPEN | Protected bootstrap, custody and transfer |
| Pre-import/coverage/meaning | Source-only loader, envelope coverage, token/rollback and native meaning/loading unresolved | OPEN | Scoped implementation/verification as authorised |
| Existing pilot | No changes; health not rechecked | Historical only | No live health assertion |
| Protected release | Offline PASS; observation defects fixed offline; native gates open | NO GO | Keep optional guard draft/parked |



Status: installer implemented on the candidate branch, with native component evidence; not an installation approval. Follow [installer acceptance](installer-testing.md) for the required evidence and report. Complete two-account client use, secure handoff and protected recovery remain release gates.

The public `code23/agent-memory-kit` repository stays the distribution and documentation home. Preserve its Git history and previous file-vault implementation while replacing the default onboarding only when the new path is actually installable. The client runs memory on their own Mac; no hosted deployment is implied.

## Frozen acceptance

- One Mac walkthrough names every required tool, account, permission, credential context and command. It has no undocumented database/role preparation step.
- Reuse the existing `log this` entry point and the existing three-model YOLO workflow. Do not create a second memory store or silently reroute personal capture.
- Ship the tested runtime with complete licensing/provenance and reproducible source access. The six-file runtime verifier remains strict.
- Setup detects missing prerequisites before mutation, refuses existing nonmatching configuration, stores no credentials in ordinary files or arguments, and preserves business data outside the checkout.
- Decide and verify the Mac OS administration boundary. A same-account unsandboxed agent is not isolated by environment variables, separate terminals, Keychain labels or Docker.
- Rehearse installation, pending capture, protected exact-content approval, restart/fresh-session recall, withdrawal, access revocation and service outage through the actual installed command/client.
- Rehearse the protected backup/recovery and upgrade path. Keep offline archive activation disabled until current authority is reconciled.
- Run repository checks and independent review before public default-branch replacement. Publish no secrets, private paths, client data or unverified compatibility claims.

## Delivery order

1. Preserve the current public baseline and create the feature branch.
2. Package the existing tested runtime and licenses; provide its exact source revision and rebuild path.
3. Complete the Mac provisioning/profile/binding implementation selected by the administration decision.
4. Make [mac-setup.md](mac-setup.md) the exact novice walkthrough, replacing every unfinished step with a checked command or explicit human action.
5. Verify in a clean non-production Mac context, complete independent review and repository checks, then push/update the public repository with a clear version boundary and legacy/migration guidance.

The before/after quality benchmark is deferred at the user's request. Essential installation, security and regression checks remain part of release acceptance.

## Historical baseline instruction and capture compatibility

**Blocked: the candidate cannot adopt an existing global instruction or personal
capture context.** Preserve those files, the current native configuration
selectors and the three-model workflow. Do not delete or move instructions, use
an empty native configuration directory, or add an acknowledgement flag to bypass
the refusal. Successful service installation is not project-context approval.

The current project profile contains coding-user-owned managed-region checksums.
They detect inconsistent edits; they are not an operator's approval. That user
can regenerate the profile and matching managed blocks. The operator's existing
installation root is private and cannot supply a coding-user-readable approval
record. No protected context issuer, mandatory record lookup, revocation or
reviewed capture-dispatch contract is implemented. A signed file referenced only
by the mutable project profile would not solve omission or old-record replay.

The managed block currently treats `logthis` as business capture in its supported
clean test context. It does not prove that a pre-existing personal entry point
keeps its default or that explicit business intent wins unambiguously in a real
native client. Native selectors are read from the current environment, and the
wrapper launches the requested command unchanged. Its checks are not immutable
context attestation or confinement of independently launched clients.

| Existing boundary | Current behavior |
| --- | --- |
| `doctor`, `plan`, `install`, operator `status` | Validate or operate the protected service; do not approve a coding project's instruction/capture context |
| `connect-check`, `connect`, `reconnect`, `run` | Refuse the unsupported global/capture paths through shared client checks; managed hashes establish consistency only |
| Rotation and interrupted binding recovery | Preserve the existing workspace, exact managed regions and concurrent edits; neither creates reviewed context authority |
| Operator uninstall | Preserves data, configuration and credentials; it is not project unbinding. No client `unbind` command is implemented |

Before this gate can pass, a separately reviewed contract must establish:

1. An authorized operator's review of the exact full instruction/capture context,
   including the supported client's loading rules and selected configuration
   directories. The current path-existence checks never authorize reading private
   bodies. Such review needs explicitly authorized sources and handling.
2. Current protected authority outside coding-user-writable state, bound to the
   coding UID, project identity, workspace/service, software/client contract,
   selectors and complete approved context. Missing, changed, stripped, revoked
   or replayed authority must refuse at every affected lifecycle boundary.
3. Reuse of the existing capture entry point: unscoped/personal capture retains
   its existing route; only explicit business selection proposes pending facts.
   No second command, store, model service or automatic publication is required.
4. Synthetic failure-path evidence followed by the named two-account,
   unlocked-Keychain and actual-client acceptance. Wrapper tests cannot certify
   native loading or a host custody boundary that was not exercised.

No filename whitelist, coding-owned review flag or partial profile-format change
is approved as a substitute. Until this contract and its fixtures exist, leave
the integration stopped in an existing incompatible context. The current safe
refusal and isolated clean-fixture tests are not a client-readiness verdict.

### What the local evidence establishes

Historical verification recorded offline and packaged runtime passes. The latest
full-kit attempt recorded installer failures/errors under strict archive guards;
no full-suite pass is claimed for the local observer candidate. The
[client regression tests](../tests/test_installer_client.py) exercise clean
preflight/connect, a real Python child, rotation/reconnect and another child,
preserving fictional model/routing settings and unrelated configuration. Existing
global instructions or personal capture cause initial and bound lifecycle checks
to refuse without changing fixture bytes or reaching credential/child effects.
No actual native coding client or private instruction body is used.

Separate isolated diagnostic witnesses confirm why those checks are not approval:
the coding user can regenerate matching profile/managed-region checksums; clean
native selectors can drift between calls; and context can appear after
verification but before the mocked child boundary. The next check refuses that
context, but no immutable launch-custody guarantee follows. These are blocking
limitations, not successful compatibility or server-authorization tests. These baseline results are historical. The local observer below adds the separately approved admission mechanism.

### Operator-controlled authority: approved local observation contract

The narrower observed-context approval mechanism is authorised. A conservative
local Claude Code 2.1.318 observer now has a passing fictional integrated workflow.
Independent final code review and full-suite validation remain pending; this is
not native-client or installation acceptance. Independent contract challenge found the mechanism viable
at the protected launcher's authorisation points, but blocked the stronger
requirement to deny every concurrent context edit before child creation. Checks
cannot freeze coding-owned files between their final read and the native client's
later reads. A cooperative registry lock does not close that interval.

The registry would be a safety interlock on one protected launcher. It would not
confine an unsandboxed coding account, certify independently launched clients or
turn prompts into an authorisation boundary. Server membership, restricted
read/submit tokens, token revocation and protected publication review remain the
actual memory authority. Revoking context approval cannot revoke a token already
held by a running process.

| Candidate | What it could establish | Missing decision or access |
| --- | --- | --- |
| Approval at the protected launcher's decision points | Exact reviewed inventory matches the bytes observed during each current approval lookup; admit/revoke replaces blanket refusal | Narrower guarantee accepted; complete native loading contract and workflow still unimplemented |
| Immutable client adapter | Supported client consumes only a supplied immutable context | Vendor-documented loading/discovery controls and a named authorised native fixture; substituting an empty configuration directory remains forbidden |
| Operator custody or host sandbox | Coding processes cannot alter the context being consumed | Separate host/security authority and an agreed change to the coding workflow |

The first option is approved with acceptance frozen below. Edits after the final
observation, later native loading and independently launched clients are outside
its guarantee. The first invented-client draft did not meet that acceptance and remains stopped.
The source-backed local observer is a distinct bounded implementation of it:

- **Fixed custody and discovery.** A root-owned discovery directory under
  `/Library/Application Support/Agent Memory Kit/Context Authority` delegates a
  client-readable, operator-owned subtree for protected client software and the
  current registry. Every ancestor must prevent replacement by the coding
  account. Its real creation needs separately authorised host setup. The private
  service root stays private. Profile fields and inherited environment cannot
  choose or omit this authority. Lifecycle commands refuse an unprotected copy
  of the software. Descriptor-anchored registry reads check the operator owner,
  file type, inode, ACL and ownership-enforcing volume; the existing stricter
  project-file/private-root checks must not be relaxed to read public metadata.
- **Complete observed context.** Protected software builds an inventory from a
  versioned loading contract for each supported client. The operator cannot
  omit sources by selecting a list. It records absent paths and complete
  supported instruction, import, skill, command, prompt, agent, plugin and
  settings trees. Unknown loading mechanisms refuse. A familiar filename is
  not evidence that competing capture instructions are absent. Only explicitly
  authorised bodies may be read or displayed; current development fixtures use
  fictional sources exclusively. Credentials are excluded, not copied or hashed
  into a context packet. Unclassifiable inputs stop intake.
- **Exact review and launch identity.** Extend the existing read-only preflight
  and operator command structure to stream a canonical context inventory over
  the established transport. The operator re-hashes the displayed authorised
  bytes and confirms their digest through the protected terminal, without an
  approval flag or new capture store. Bind coding UID, canonical project path
  and device/inode, workspace/service, native selectors, context-affecting
  environment and arguments, resolved client executable/package identity,
  protected software digest, loading-contract version and complete inventory.
  Preserve ordinary model/routing arguments; refuse unreviewed context-affecting
  values, unknown clients and binary/version drift. Binary hashes are observed
  identity, not custody of a coding-owned executable.
- **Current lookup and effects.** Give each approval a current generation in the
  protected registry. Missing, malformed, stripped, changed, revoked or old
  authority refuses at `connect-check`, initial and already-bound `connect`,
  `reconnect` and `run`, before credential, project-write or child effects at
  that decision point. Rotation and interrupted recovery do not mint approval.
  Record all intended prospective managed bytes during review, so binding cannot
  silently introduce unreviewed instructions. Recheck changes during an operation;
  report post-session drift separately, without claiming it was prevented.
- **Revocation and races.** Revoke publishes a new revoked generation atomically
  without waiting indefinitely on a coding-readable lock. Launch takes a shared
  lock only through the bounded authorisation/spawn interval, never while waiting
  for the session. Operator synchronisation attempts are bounded and report any
  unconfirmed in-flight launch. Tests must cover parent and symlink replacement,
  malformed inputs, stale generations, concurrent editing, atomic replacement,
  maliciously held locks and parallel revocation. A final read still does not
  freeze files or establish immutable native consumption.
- **Existing capture dispatch.** Preserve personal or unscoped capture on its
  previous route. Only explicitly selected business capture proposes pending
  facts through the same entry point; it never approves or publishes. Review
  the exact generated block with the rest of the context. Deterministic tests
  assert observable effects and structured contracts. A versioned, opt-in LLM
  meaning rubric and an actual supported native fixture remain separate gates;
  keyword matching cannot certify intent or personal-route coexistence.

Synthetic acceptance would exercise operator review, preflight, connect, a real
controlled child, rotation/reconnect and revoke or changed-context denial,
preserving fixture bytes, personal/default dispatch and model choices. It must
exercise each failure path above before credential/write/child effects, while
labelling mocks of UID/custody checks as mocks. Passing this would not establish
a real two-account boundary, unlocked-Keychain transfer or native loading.
Those require named authorised fixtures and remain unrun. No host bootstrap, client installation or mutable-profile bypass is part of
the evidence. Final independent code review remains required.

### Local observer candidate and limits

The invented-client attempt was stopped and removed. The implemented contracts are
exactly `claude-code/2.1.318` and `claude-code/2.1.319`, based on the official
[memory](https://code.claude.com/docs/en/memory),
[settings](https://code.claude.com/docs/en/settings),
[managed policy](https://code.claude.com/docs/en/managed-settings),
[server policy](https://code.claude.com/docs/en/server-managed-settings) and
[CLI](https://code.claude.com/docs/en/cli-reference) documentation plus bounded
shipped release metadata inspection. Native binary identity binds resolved path,
embedded release metadata and observed SHA-256; it is not custody or authenticity
attestation. SHA-256 binds reviewed bytes, not vendor authenticity. No invented
executable protocol is exposed. The resolved `versions/<version>` path name and
embedded VERSION marker must agree; unknown versions refuse without fallback.
Packets record the actual selected contract. Operator packet validation checks
only the recorded executable identity's self-consistency, without resolving or
reading the coding user's executable. Authorization at launch freshly observes
the executable as the coding user and refuses a changed contract, executable
version, resolved path or SHA-256; an executable change requires fresh review.

**2.1.319 observer candidate:** qualification rests on changelog review and binary
string comparison. This is triage, not proof of identical loading behaviour.
The review observes specific discovery slots; coverage remains unproven. The
guarantee remains **reviewed local observations during the authorization lookup**,
without an immutable-filesystem claim or proof of later native consumption.
2.1.319 contains security fixes for a Bash permission bypass and a sandbox escape;
2.1.318 is retained only for compatibility, not recommended. Version control via
`requiredMinimumVersion`/`requiredMaximumVersion` managed settings is future work
because the observer currently refuses nonempty managed policy. The existing
version-matched native rehearsal remains required and unrun for this candidate.

The prototype observes its enumerated system/user instructions, managed
settings/drop-ins and preference paths, selected native configuration, governing
ancestors, descendant discovery slots and supported recursive trees. Independent
review found remaining local-source coverage gaps; this is not a complete native
context inventory. Missing supported slots are explicit.
Known credential files are presence-only exclusions, never hashed or displayed.
The local remote-policy cache is observed when empty; active unclassified cache
or signature metadata refuses. Remote fetching itself is outside the boundary.

This conservative subset refuses imports/dynamic Markdown/frontmatter, nonempty
plugins/managed policy, context-affecting or unknown mixed account-state keys, managed preferences,
unknown settings/context arguments/injection environment, linked worktrees and
unclassifiable support files. Auto-memory must already be explicitly disabled in
the selected native user's `settings.json`, with no contrary observed setting;
the mechanism never disables it or substitutes a clean home. The fixed
`auto-memory-disabled/v1` entry records only presence of the known `projects`
root. It never enumerates its project names or reads, copies or hashes memory
bodies. Its exact enum, boolean type, fixed path and disabled-policy prerequisite
are validated and bound in current/prospective approval. It cannot classify an
arbitrary active input as inactive. This local disabled-policy observation does
not certify what a native client later loads.
Native model and permission arguments remain unchanged. Existing native auth stays
in the child environment and is absent from review packets/registry.

Current registry lookup is mandatory for preflight, initial and already-bound
connect, reconnect and run. Review includes exact prospective managed bytes.
Approval/revocation increments generation atomically. The operator lock must be
0600; packet-free revoke consults protected state. After terminal confirmation it
attempts the exclusive launch lock for at most 0.2 seconds before publication.
When acquired, that lock spans atomic publication. Otherwise publication proceeds
and uncertainty stays true even if a shared lock releases during publication.
A held readable shared lock cannot indefinitely block revocation publication.
The launch lock is released after child creation, before waiting.
`in_flight_launch_uncertain` covers only the authorization/child-creation window;
`false` does not mean no session is running. Revocation never stops an existing
session or removes the token already inherited by that process. This first
version supports one active project per delegated registry; changing project
requires explicit revoke. The fixed discovery/bootstrap remains an unrun host gate.

The integrated fictional workflow passed: canonical terminal review, issue,
read-only preflight, initial/bound connect, actual controlled Python child,
rotation/reconnect, another child, context-edit denial before effects and
packet-free revoke/denial. Native resolver/source roots/UID/custody are explicit
mocks. Structured capture directives retain default/personal on the previous
route and select only explicit business `memory_submit` pending proposals. This
checks the fixture protocol, not native LLM meaning. Final full-suite validation,
independent code review, actual native loading and real two-UID/Keychain gates
remain open. Historical failures/repairs and the missed first milestone remain
retained in external task evidence.

### Targeted privacy and revoke corrections; prototype still held

Focused regressions reproduced both confirmed defects before correction:
unrelated project-memory enumeration, and false revoke certainty when a separate
process releases its shared lock during publication. The repaired guarded fixture
preserves the full approve/preflight/connect/bound-connect/real controlled Python
child/rotation/drift-denial/packet-free-revoke workflow. Neither foreign text nor
project names appear in its packet or registry. Additional tests reject malformed
inactive entries, re-enabled or missing selected-user policy and inactive tags
for other paths. A separate process proves the exclusive lock spans uncontended
approval and revoke publication; a malicious held lock cannot prevent bounded
publication. These are explicitly mocked native identity/root/UID/custody/TTY
fixtures, not native or two-account acceptance.

The bytecode investigation remains an open pre-import gate. A harmless fictional
module demonstrated that Python `-I -B` reads a matching existing `.pyc` while
source bytes and the current `software_hash()` remain unchanged. The launcher
imports kit code before `authority()`; a later tree check cannot undo code already
executed. No launcher, host or security implementation was changed in this repair.
A trusted pre-import bootstrap/source-only loading path and protected provisioning
need a separate bounded implementation and independent validation before this
prototype can claim protected software execution.

Independent observer/authority/lifecycle reviews returned changes needed. Local
OS preference/git coverage and aggregate bounds, possible token-reference reuse,
and inherited rollback/post-effect reporting concerns remain open or unqualified.
The restrictive-umask usability gap remains open; the claim that umask002 turns
0644 into 0664 was incorrect and is not a defect being patched. No new exclusions
hide local active inputs. The approved observed-launch boundary and server
role/token/publication authority are unchanged. This partial correction is not
whole-context completion, code approval, installation or release readiness.

#### Scoped review closure: namespace admission and revoke failure paths

Independent privacy review found the metadata-only memory-root repair insufficient:
a selected custom native config below a valid project could still be reached by
its generic descendant walk. That approach is stopped. The bounded recovery now
refuses config/project overlap before any context body read or source walk, using
canonical directory identities and no-follow metadata opens. Config aliases and
linked ancestors also refuse. Packet intake applies the same admission. Nothing
is pruned or relocated, no native selector is changed, and the inactive tag still
cannot hide an active source. The regression uses a valid project and poison
`CLAUDE.md`/`AGENTS.md` foreign cache files; the review's project-equals-HOME example
would already be refused by the public project validator.

The independent revoke-certainty review passed its scope. Additional hardening
now ensures revoke publishes its revoked next generation with uncertainty even if
launch-lock opening/validation or non-contention flock acquisition fails. Approval
still refuses these failures. Publication/flush/fsync errors are outside that
catch and still propagate; repairing the lock does not restore old approval.
The private operator lock, packet-free revoke, bounded wait and lock ownership
across successful publication remain intact. Independent native Claude Opus 5.5
review passed both the certainty correction and the acquisition-error hardening,
strictly within their stated scopes. No overall prototype approval follows.

#### Final disposition: privacy approach stopped

A further isolated fixture exposed a remaining alias route: a native `projects`
cache link can point into the coding project, and the project walk attempts the
foreign instruction read before the later cache-link rejection. No real private
data was accessed. The privacy approach is stopped and remains unapproved; the
passing scoped regressions do not establish the general privacy invariant.

Keep the prototype uninstalled. The revocation corrections have scoped review
acceptance; privacy, broader local-source coverage and real host acceptance remain
open. The bytecode fixture establishes missing integrity coverage where files are
writable, not an exploit of a fresh protected installation: the fresh copier
excludes caches. Source-only loading is a reviewed feasible design, not an
implemented or certified loading boundary.

### Read-order planner redesign (local candidate)

The earlier late-root checks are stopped as insufficient. A recorded fictional
witness showed `config/projects` linked into a project cache reaching poison
instructions before rejection. The observer now builds a metadata-only plan:
no-follow/type admission of the inactive root and all fixed source, empty-only
and traversal roots precedes enumeration. Recursive discovery records slots and
absences without `_classified` or binding reads; only the completed plan is
materialized through the existing `_read`/classification protections. Metadata is
rechecked before reads and around binding preparation/verification. Profile and
managed binding paths are planned too. Early profile/fallback readers use the
same metadata planner before reading; external CLI/API options stay unchanged.

This refuses linked roots, ancestor skill aliases and inactive/recursive namespace
overlap rather than pruning active sources. The inactive directory is inspected
through its parent without opening/listing private children. Exact alias and
no-body-before-plan regressions, phase-boundary drift/addition checks and the
controlled Python-child lifecycle provide local evidence only. Accepted revoke
code is unchanged. Native loading, real custody/host setup and the other coverage
and loader findings remain unqualified; independent Claude code review is still
required. The design review returned aborted streaming and NO VERDICT.

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

## Whole-candidate repair, 9 November 2026 (offline)

The guarantee remains **reviewed local observations during the authorization
lookup**. No immutable filesystem or later native-consumption claim is made.
Rollout stays **NO GO**. The real two-UID boundary is untested because the native
rehearsal is not being run (James, 9 November 2026). No installation, account,
host-permission or live-pilot change is part of this repair.

Operator `validate_packet` checks typed recorded identity, canonical absolute
path spelling, namespace separation and packet self-consistency only. It never
opens or stats the coding user's project/configuration/executable paths. The
coding user's `decision()` independently re-observes sources before registry
comparison. The simulation denies coder-path opens, body reads and metadata
probes throughout operator validation/publication; it then restores the coder's
view and verifies changed instructions refuse. The real `authority()` has direct
unit coverage for delegation key set/version, both UID floors/types, distinct
UIDs and exact coding-UID match; root custody and account identities remain mocked.

### Mixed Claude Code account-state classification

For `~/.claude.json`, `$CLAUDE_CONFIG_DIR/.claude.json` and the selected
`<config>.json` sibling, the chosen design is **refusal**, rather than packet
inclusion, for context-affecting keys. Their presence refuses even with an empty
value. Unknown keys also refuse. `projects` is a structural container only:
every project's entry must be an object with only the project inert keys below.
Inert account/UI/metrics values are opaque and stay local: neither their text,
values, project names nor a digest of their changing values enters the packet or
registry. A fixed `inert-claude-state` / `keys/v1` marker records classification;
normal startup-counter changes therefore do not invalidate approval. Full planned
metadata checks still catch concurrent state-file changes during observation.

Sources: the official [settings files and precedence](https://code.claude.com/docs/en/settings)
and its [settings reference](https://code.claude.com/docs/en/settings-reference),
plus [MCP scopes, project approvals and server enablement](https://code.claude.com/docs/en/mcp),
read on 9 November 2026. These describe loader scopes, account state, global
configuration, MCP definitions and approvals; they do not publish a complete
internal-state schema. The conservative inert inventory below was selected from
**key names only** in the local `.claude.json` on that date. No local account
values or per-project path names were printed, logged or stored. This is a
maintained subset for 2.1.318/2.1.319, not general compatibility with every file
Claude Code writes. Caches, trust flags and other unclassified fields may still
refuse normal installations; never delete them or select a clean profile to bypass
refusal. Documented context keys absent from the explicit refusal set still
refuse through the unknown-key rule.

Top-level inert allow-list (`INERT_STATE_KEYS`):

`announcementImpressions`, `anonymousId`, `birthdayHatAnimationCount`, `btwUseCount`
`changelogLastFetched`, `claudeCodeFirstTokenDate`, `diffSidebarOpen`, `effortCalloutDismissed`
`effortCalloutV2Dismissed`, `feedbackSurveyState`, `firstStartTime`, `hasCompletedOnboarding`
`hasIdeOnboardingBeenShown`, `hasSeenEffortMediumNudgeByModel`, `hasSeenStashHint`, `hasSeenTasksHint`
`hasUsedBackslashReturn`, `hasUsedStash`, `ideHintShownCount`, `installMethod`
`lastClawdEntranceVersion`, `lastOnboardingVersion`, `lastReleaseNotesSeen`, `lastShownEmergencyTip`
`machineID`, `migrationVersion`, `numStartups`, `oauthAccount`
`promptQueueUseCount`, `seenNotifications`, `shiftEnterKeyBindingInstalled`, `showSpinnerTree`
`subscriptionNoticeCount`, `tipLifetimeShownCounts`, `tipsHistory`, `tipsHistoryByCommand`
`userID`

Per-project inert allow-list (`INERT_PROJECT_STATE_KEYS`):

`lastAPIDuration`, `lastAPIDurationWithoutRetries`, `lastCost`, `lastDuration`
`lastFpsAverage`, `lastFpsLow1Pct`, `lastGracefulShutdown`, `lastLinesAdded`
`lastLinesRemoved`, `lastModelUsage`, `lastSessionId`, `lastSessionMetrics`
`lastSessionModified`, `lastStartTime`, `lastToolDuration`, `lastTotalCacheCreationInputTokens`
`lastTotalCacheReadInputTokens`, `lastTotalInputTokens`, `lastTotalOutputTokens`, `lastTotalWebSearchRequests`
`lastVersionBase`

Explicit context refusal keys at either scope (`CONTEXT_STATE_KEYS`):

`additionalDirectories`, `allowedMcpServers`, `allowedTools`, `autoConnectIde`
`autoInstallIdeExtension`, `autoMemoryDirectory`, `autoMemoryEnabled`, `autoUpdates`
`autoUpdatesProtectedForNative`, `chromeExtension`, `claudeInChromeDefaultEnabled`, `defaultToAgentsView`
`deniedMcpServers`, `disabledMcpServers`, `disabledMcpjsonServers`, `enableAllProjectMcpServers`
`enabledMcpServers`, `enabledMcpjsonServers`, `enabledPlugins`, `env`
`exampleFiles`, `exampleFilesGeneratedAt`, `externalEditorContext`, `extraKnownMarketplaces`
`hasClaudeMdExternalIncludesApproved`, `hasClaudeMdExternalIncludesWarningShown`, `hasTrustDialogAccepted`, `hasTrustDialogHooksAccepted`
`hooks`, `ignorePatterns`, `managedMcpServers`, `mcpContextUris`
`mcpServers`, `model`, `permissions`, `remoteControlSpawnMode`

Settings outside this mixed-state file retain their existing conservative
classification: models/limited permissions/disabled auto-memory are reviewed;
other settings, hooks, plugins, environment sources, imports, managed preferences,
remote caches and unsupported sources refuse. This repair adds no context-source
bypass and never reads native credentials to classify them.

### Cost and credential exposure

Observation now makes three full plan checks: after discovery, immediately
before source bodies, and after the final binding/source read. The two middle
checks were removed; the shared per-path/descriptor identity guards remain active.
A `run` still performs an early metadata plan and two `decision()` observations:
seven full checks instead of eleven. Each check still walks every planned path's
ancestors; cost grows with path count and depth, and native executable hashing
still occurs per observation. No large-repository timing claim is made. Supported
projects are ordinary owned directory trees without descendant symlinks; common
`node_modules/.bin` and `.venv/bin` links can still refuse the whole project.

The token is stored in Keychain and passed in `AGENT_MEMORY_TOKEN` in the native
child's environment. Its subprocesses inherit it and can print it into plaintext
Claude transcripts or send it elsewhere. The installer does not prevent this.
The bundled MCP server exposes read tools and, only for `read_submit` with
submissions enabled, pending submission. Its API requires the credential's exact
single workspace and supplies no approval/publication capability to that bot.
These are source observations, not a new live token/authorization test.

Only software files on disk are protected by delegation. A cooperative coding
process performs the interlock; refusing `PYTHON*` inside Python does not undo
startup imports or protect the already-running interpreter.

### Open findings after this repair

- Context 4 residual: parent walks and conservative symlink refusal remain; a larger discovery/performance redesign is outside this bounded repair.
- Context 6 residual: revoke output gains no new field/message; the existing field is documented as authorization-window certainty to avoid changing the CLI response contract.
- Context 8 residual: the explicit 0644 registry remains readable by all local users and discloses project metadata, PATH and argv; a coding-user-only ACL needs separately authorized permission/bootstrap work.
- Context 11: the bounded canonical JSON terminal view remains cumbersome; review presentation needs a separate operator-UX change.
- Host 3: PostgreSQL support files/dylibs and Python site-package trust need a wider prefix/loader audit; host changes here are limited to requested findings 1, 2 and 5.
- Host 4: lifecycle test custody mocks remain; changing them is outside the explicitly limited host repair, and does not replace real two-UID acceptance.
- Native loading/lifecycle, discovery completeness, protected bootstrap, two-account Keychain transfer and host recovery remain untested release gates; the rehearsal is not being run.
- No new model review was requested or run, per this repair's instruction; the earlier whole-candidate reviews remain the source of these finding IDs.
