# Capability detection

Know what you can really do before planning. Check once per session; reuse the result.

## What to establish

| Capability | How to tell |
|---|---|
| Read / write files | A file tool is listed, or a harmless read succeeds |
| Shell | A command tool is listed; `echo ok` returns `ok` |
| Runtimes | `python3 --version`, `node --version`, … (only those the task needs) |
| Tests | Test config present (`pytest.ini`, `package.json` scripts, `Makefile`…) |
| Web / sources | A search or fetch tool is listed |
| Documents | A document/office tool or library is available |
| Persistent memory | A memory tool, or a writable workspace that survives the session |
| Sub-agents | An agent/delegation tool is listed |
| Permissions | What needs approval; sandbox or network limits stated by the platform |

Rules:

- A tool exists only if it is listed or a probe succeeded. An example in a document is not proof.
- A failed probe is a fact: record it, do not retry the same probe in a loop.
- Do not probe things the task does not need.

## Helper script

When a shell and Python are available:

```
python3 scripts/detect_capabilities.py            # human summary
python3 scripts/detect_capabilities.py --json     # machine-readable, schemas/capabilities.schema.json
```

It only inspects the local machine (PATH lookups, `--version` calls, file presence). It sends nothing over the network and changes nothing. It cannot see the tools an AI platform grants the model (web search, memory, sub-agents): add those yourself from the tool list you were given.

## Without a shell

Write the capability summary by hand from your tool list, mark everything else `unknown`, and say in the final report which checks this prevented.
