# Team setup

One shared memory repository for the whole team. Everybody's agents read it. Very few
things write to it.

## One repository

Create a single git repository for the memory, laid out as in `docs/folder-layout.md`.
Keep it separate from your code repositories so that access to memory is a deliberate
decision. Give every agent and every person read access to the vault folder. Keep the
memory repository local or on a private host. Do not make it public.

## Who can promote

Promotion is the only write path to trusted memory. Decide who or what may do it.

| Role | Can do |
|------|--------|
| Agents and people | Read trusted. Propose to staging. |
| Promoting tool (the funnel) | Promote eligible proposals. Needs evidence, the lock and a commit. |
| Reviewer (a named person) | Approve or reject parked proposals. Review promotion commits. |
| Owner | Change policy, scopes, deny lists and who the reviewers are. |

A small team can make one person the reviewer and the owner. Write the names down in the
repository README so nobody has to guess.

## Two ways to run promotion

**Lock based.** One machine runs the funnel on a schedule. Promotion takes the write lock,
commits locally and the reviewer pulls or reads the history. Simple, and fine when one
machine owns the memory.

**Branch and pull request.** Proposals arrive as a branch or pull request that adds files
to the candidates folder. A promotion job (or a reviewer) checks the proposal, and merging the
request is the promotion. The merge commit is the audit trail. Use this when several
people write proposals from different machines. Protect the main branch so only the
promoting job and reviewers can merge.

Pick one. Do not run both against the same repository.

## Per-client folders

Give each client its own page, or its own folder once it needs more than one page:

```
vault/03-resources/agent-systems/
  captured-client-northwind-studio.md
  captured-client-harbour-bakery.md
```

Use the scope grammar `client:<slug>`. The registry maps each scope to exactly one
destination, so a fact about one client cannot land on another client's page by accident.

## Keeping client data separate

- One scope per client, one destination per scope. Unknown scopes park for review.
- Store facts about how you work with a client, not the client's data. No customer lists,
  invoices, credentials or personal data.
- Team routing is off by default. To use it, set `MEMORY_TEAM_ROUTING=1` and set
  `MEMORY_TEAM_BIN` to the absolute path of your team-store command (it is never looked up
  on `PATH`). Even then only scopes you list in `team_share_scopes` in the registry are
  copied; anything unlisted is refused, and `team_exclude` can veto a listed slug. Mark
  private facts so they never leave the local memory.
- If an agent works for one client, only give it the router index and notes for that
  client. The router can be restricted to a folder with `--allow-root`.
- Do not mix clients in one proposal. One fact, one scope.
- If two clients must never be visible to the same people, use two repositories.

## When people leave

1. Remove their access to the memory repository and to the machine that runs the funnel.
2. Rotate any shared credentials they had. None should be in the memory, so this is
   a check, not a clean up.
3. Review the promotion commits and proposals they made in their last month. Revert
   anything you cannot stand behind (`docs/maintenance.md`).
4. Reassign their pages and any parked proposals to another reviewer.
5. Update the reviewer list in the README and the policy file.
6. Their facts stay. Facts belong to the team and carry a source, so they remain valid
   when the author leaves. Remove a person's name from a fact only if the fact itself
   would be wrong or unsafe without it.
