# First Mac client release

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

## Existing instruction and capture compatibility

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

The offline suite and packaged runtime verifier pass. The
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
limitations, not successful compatibility or server-authorization tests. Runtime
behavior and the existing refusal remain unchanged.

### Operator-controlled authority: decision before implementation

A protected operator registry is a new candidate, not an implemented exception
to the refusal above. Independent contract challenge found the mechanism viable
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
| Approval at the protected launcher's decision points | Exact reviewed inventory matches the bytes observed during each current approval lookup; admit/revoke replaces blanket refusal | Explicit acceptance of later edits and native loading as unaccepted; required contract below must be implemented and tested |
| Immutable client adapter | Supported client consumes only a supplied immutable context | Vendor-documented loading/discovery controls and a named authorised native fixture; substituting an empty configuration directory remains forbidden |
| Operator custody or host sandbox | Coding processes cannot alter the context being consumed | Separate host/security authority and an agreed change to the coding workflow |

No implementation acceptance is frozen until that decision is resolved. The
first option needs all the following; it is not a profile flag or filename
exemption:

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
Those require named authorised fixtures and remain unrun. No host bootstrap,
client installation, mutable-profile bypass or runtime implementation is part
of the evidence for this design decision.
