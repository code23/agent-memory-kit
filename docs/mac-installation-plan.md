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
