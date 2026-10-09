# Platform notes

**Read this table honestly.** "Agent Skills format" means the platform's own documentation (as listed on the Agent Skills client showcase, agentskills.io/clients, consulted 2026-10-09) says it supports the format. **It does not mean OMNISKILL was tested there.** The "OMNISKILL tested" column changes only when a benchmark run on that platform is committed in `benchmarks/results/`.

| Platform | How to load | Agent Skills format | OMNISKILL tested |
|---|---|---|---|
| Claude (claude.ai, apps) | Upload the skill folder as a custom skill, or paste a bundle in project instructions | Listed | No |
| Claude Code | Folder in the user or project skills directory | Listed | No |
| Claude API | Skills via the API, or a bundle in the system prompt | Listed (platform docs) | No |
| ChatGPT & Codex | Codex: skills directory; ChatGPT: bundle in custom instructions or a GPT/project | Listed for "ChatGPT & Codex" | No |
| Gemini CLI | Skills directory, or `GEMINI.md` pointing to the skill | Listed | No |
| Gemini app | Bundle pasted as instructions (Gems) | Not listed | No |
| DeepSeek | Deep Code CLI skills directory; chat: paste a bundle | Deep Code listed | No |
| Qwen | Bundle in system prompt; Qwen-based agents that support skills | Not listed as such | No |
| Ollama / local models | Bundle in a Modelfile `SYSTEM` block or the client's system prompt; skill-capable agents (e.g. Goose, OpenCode) with a local model | Via the agent, not the model | No |
| Cursor, GitHub Copilot / VS Code, OpenCode, Goose, Junie… | Skills directory per their docs, or project instruction file | Listed | No |

Install paths and UI labels change; follow each platform's current skills documentation rather than a path copied here.

## Local models (Ollama example)

```
python3 scripts/bundle.py --mode quick --stdout > omniskill-quick.md
```

Then in a Modelfile:

```
FROM qwen2.5:14b
SYSTEM """<paste omniskill-quick.md here>"""
```

Small models follow long instructions less reliably: start with the QUICK bundle (~1,900 tokens) and measure before using larger ones.

## Known differences to document when testing a platform

- Does it load `SKILL.md` automatically, on demand, or not at all?
- Can the model read `modes/` and `references/` files after loading the core?
- Can it run `scripts/` (which runtime, which approval flow)?
- Does it expose token counts and tool-call counts for the benchmark?
- Where can AUTONOMOUS checkpoints persist?

Record the answers in `benchmarks/results/<run>/CONDITIONS.md` with the run.
