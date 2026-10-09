# Generic adapter

Works with any assistant that accepts text instructions, with or without tools.

## Option 1 — the platform loads Agent Skills

Copy the whole `omniskill/` folder (the directory name must stay `omniskill`, it must equal the `name` field) into the platform's skills location. The platform reads the `name` and `description`, loads `SKILL.md` when a task matches, and the core then points to the mode and reference files. See `adapters/platforms.md` for known locations.

## Option 2 — paste a bundle

For chat products, custom instructions, system prompts, API calls or local models:

```
python3 scripts/bundle.py --mode pro --with-evidence --stdout > omniskill-pro.md
```

Paste the file content into the system prompt / custom instructions. Choose the mode you use most (`pro` is a sensible default); bundles are ~2,000–2,600 tokens with the evidence protocol. No Python? Concatenate `SKILL.md` (without the `---` header) and one `modes/*.md` file by hand.

## Option 3 — project instruction file

Coding agents that read a project file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`…) can point to the skill:

```markdown
## Working protocol
Follow `omniskill/SKILL.md` for every non-trivial task: pick a mode, define acceptance
criteria, verify with evidence, end with an OMNISKILL status report.
Before running a shell command that deletes, pushes or publishes, check it with
`python3 omniskill/scripts/guard_command.py "<command>"` and ask the user when it says confirm or deny.
```

Template: `adapters/AGENTS.md.template`.

## What changes between environments

| Aspect | Varies how |
|---|---|
| Loading | Automatic skill discovery, manual paste, or a project file read at session start |
| Tools | Some have shell and files, some only chat. The core works without tools (section 10) |
| Permissions | Approval prompts are the platform's; OMNISKILL adds "ask first" rules on top, never removes the platform's |
| Persistence | AUTONOMOUS checkpoints need a writable workspace that survives the session |
| Sub-agents | Only where the platform provides them; the 3-agent cap still applies |

Never assume one platform loads the same files as another. Check that the instructions actually reached the model: ask it which status values OMNISKILL defines; it should answer VERIFIED, PARTIAL, BLOCKED, UNVERIFIED.
