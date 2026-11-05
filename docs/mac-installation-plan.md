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
