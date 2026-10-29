# aireview

Local AI git diff reviewer. `git diff` -> Ollama (`llama3.1:8b`) -> Pydantic -> Rich.

## Install
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Use (from any git repo)
```bash
aireview                 # animated review of staged + unstaged + new (untracked) files
aireview --staged-only   # review only what is staged
aireview --no-anim       # skip the logo animation
aireview --json          # validated JSON only
aireview --fail-on-risk 7   # exit 2 when risk >= 7 (CI)
aireview --trace         # after the run, print every LLM call: prompts, options, raw reply, tokens, time
aireview --trace-file t.json   # save the full, untruncated trace as JSON
```

## What the model sees
The model only sees a diff, so `get_diff()` builds it with a budget (numbers live in `src/aireview/config.py`):
- staged + unstaged + brand-new files, from the repo root; `--staged-only` limits it to staged
- source files first, then config, then docs, so code is never pushed out by a big README
- each file is cut to 3,000 characters and the whole diff to ~30k characters, derived from the 16,384-token window (`NUM_CTX`)
- lockfiles, binaries and notebooks are ignored on purpose
- if anything was trimmed or left out, the checklist says so and the result is marked **partial review**: "no issues" then only means none in what the model saw

Each call also has a reply cap (`NUM_PREDICT`) and a 120s timeout, so a rambling model fails fast instead of hanging.

## What you learn
1. **Packaging** - `pyproject.toml` + `[project.scripts]` turn a folder of Python into a command that works in any repo.
2. **Structured output** - Pydantic schemas passed to Ollama's `format=` make LLM replies typed objects, not strings.
3. **Chaining + routing** - three LLM calls where each typed output feeds the next, with plain Python (not an agent) deciding the path:

```
git diff -> [1] Review -> ReviewResult
                              |-- high/critical finding? --yes--> [2] Fix advisor -> FixPlan
                              |                            --no---> (skipped)
                              v
            [3] Commit writer (diff + review) -> CommitMessage
```

Each call takes ~1-4s on `llama3.1:8b`; small local models can be inconsistent, so treat output as advice.

## Chapter -> file map
1. Subprocess bridge: `src/aireview/git_inspector.py`
2. LLM call: `src/aireview/llm.py` (`ask()` is the one reusable structured-call helper), prompts in `src/aireview/prompts/`, limits in `src/aireview/config.py`
3. Schemas: `src/aireview/schema.py`
4. Chaining + routing: `src/aireview/chain.py`
5. Terminal UI: `src/aireview/ui.py`
6. Packaging: `pyproject.toml` (entry point `aireview = "aireview.cli:app"`)
