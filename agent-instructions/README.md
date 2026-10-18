# Agent instruction snippets

Copy-ready text that tells an agent how to read the memory, how to propose to it, and that
it must never write to the trusted folder. Pick the file for your tool, paste it into the
tool's instruction file, and replace the four placeholders:

- `<KIT>` the path to your clone of this kit (it holds `router/route.py`)
- `<VAULT_ROOT>` the trusted vault (the `vault/` folder or your private copy)
- `<ROUTER_INDEX>` the folder holding the generated router index (`$MEMORY_ROOT/router`)
- `<STAGING_INBOX>` the folder where proposals are written (`$MEMORY_ROOT/candidates`)

| Tool | Paste into | Source here |
|------|------------|-------------|
| Claude Code | `CLAUDE.md` | `CLAUDE.md` |
| Codex and other agents that read `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |
| Gemini CLI | `GEMINI.md` | `GEMINI.md` |
| Cursor | `.cursor/rules/memory.mdc` | `.cursor/rules/memory.mdc` |

The four files say the same thing in each tool's format. Keep them in step.
