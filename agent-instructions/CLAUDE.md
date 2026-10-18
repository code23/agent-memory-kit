# Memory instructions for Claude Code

Paste this into your project or user CLAUDE.md.

## Shared memory

The trusted memory is the vault at `<VAULT_ROOT>`. It is read-only for you.

### Before you start a task

1. Read `<VAULT_ROOT>/README.md` for what exists.
2. Find the relevant note with the router. Do not browse the whole memory.

   ```bash
   python3 <KIT>/router/route.py --indexdir <ROUTER_INDEX> "<what the task is about>"
   ```

3. If it prints a title and path, read that note only. If it says no relevant note was
   found, carry on without memory. Do not guess.

### While you work

- When you rely on a remembered fact, say which note it came from.
- If a remembered fact conflicts with live evidence (the code, the latest message), trust
  the live evidence and propose a correction afterwards.

### When you finish

Propose new durable facts. Do not write to the trusted folder. Ever.

- Write one file per fact into `<STAGING_INBOX>`, copying the format of
  `<VAULT_ROOT>/templates/candidate-fact.yaml`.
- Every proposal needs a source path, an exact excerpt copied from the source, and an
  observed date.
- Durable means: still true in a month and useful to a stranger. A preference, a decision,
  a rule, a boundary or a tool fact.
- Do not propose: task progress, guesses or hedged statements, anything without a source,
  or reference material that lives elsewhere.
- Never include secrets, credentials, raw transcripts, personal data, contact details or
  money figures. If a fact needs one, leave it out.

### Hard rules

- Never edit, move or delete anything under `<VAULT_ROOT>/`.
- Never run the promotion step unless a person has told you that you are the promoting tool.
- Never push the memory repository anywhere.
