# Folder layout

An example layout. The names are conventions, not requirements. The code only needs the
trusted vault, a place for the funnel's working folders, and a staging area.

```
memory-private/                   <- your private data root, OUTSIDE the kit clone
  vault/                          <- VAULT_ROOT: a git repository. Only promotion writes here.
    README.md                     <- how agents use this memory (see agent-instructions/)
    03-resources/
      agent-systems/              <- facts about how work is done
        captured-org.md           <- facts that apply across the whole organisation
        captured-client-northwind-studio.md   <- one page per client
        captured-project-website-relaunch.md  <- one page per project
      ai-memory/
        captured-personal.md      <- personal preferences
      tools/                      <- how to use tools and services
    06-maps/                      <- short maps of a topic that point at notes
    _meta/                        <- source register
    scripts/  templates/          <- lint, search, note and fact templates
  state/                          <- MEMORY_ROOT: the funnel's working folders
    policy.yaml  registry.yaml    <- your copies of the example files
    candidates/                   <- proposals waiting for review (the inbox)
    review/                       <- parked for a person
    done/  rejected/              <- history, kept for audit
    ledger/                       <- append only record of every decision
    router/                       <- generated index (disposable)
  staging/                        <- STAGING_ROOT: NOT trusted. Raw session notes that
                                     capture.py can mine, with their *.capture-state.json
                                     sidecars
```

In this kit the same ideas map to:

| Concept | In this kit | Default |
|---------|-------------|---------|
| Trusted vault | `VAULT_ROOT` | `./vault` |
| Staging | `STAGING_ROOT` | `./staging` |
| Funnel state | `MEMORY_ROOT` | `./funnel` (use a private folder in real use) |
| Router index | `router/` output folder you choose | temporary |

## Rules for the layout

- **One page per client or project.** Start with a single page. Split only when a page
  becomes hard to read.
- **Short notes with a `summary:` line.** The router ranks on titles and summaries, so a
  good summary is the best retrieval tuning you can do.
- **Trusted is append mostly.** Facts are added with a source and a date. Corrections are
  new commits, not silent edits.
- **Staging is disposable.** Delete it whenever you like. Trusted is never disposable.
- **Keep secrets out of all of it.** Credentials, raw transcripts and personal data do not
  belong in either area.
