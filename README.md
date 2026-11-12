# yt_codes

Code and notebooks for my YouTube videos on LLMs, Python tooling, and AI engineering.

## Videos

| # | Video | Published | Code |
|---|-------|-----------|------|
| 7 | Continual Pretraining (CPT) Explained \| Perplexity, Catastrophic Forgetting & Full Code (Part 2) | Nov 11, 2026 | [`llm_training/`](llm_training/) |
| 6 | How LLMs Are Trained \| Pre-Training & Post-Training Explained (Part 1) | Nov 9, 2026 | [`llm_training/llm_training_notebook.html`](llm_training/llm_training_notebook.html) |
| 5 | How to Publish a Python Package to PyPI in 2026 (Full Walkthrough) | Nov 4, 2026 | [`cli_tool/`](cli_tool/) (packaging, `dist/`, `GUIDE.md`) |
| 4 | Local LLM Code Reviewer in Python: Structured Output, Context Window, Chaining (Part 1) | Oct 30, 2026 | [`cli_tool/`](cli_tool/) |
| 3 | Run LLMs Locally AND in the Cloud: Ollama + Gemini + Build Your First AI Agent | Oct 29, 2026 | [`working_with_llms/`](working_with_llms/) |
| 2 | I Built a Self-Evaluating AI Content Generator \| LangGraph + Gemini | Aug 26, 2026 | [`harjasdt/content-system`](https://github.com/harjasdt/content-system) (external repo) |
| 1 | The 30-Year Failure That Accidentally Created Modern AI | Jun 3, 2026 |  |

## Code

| Folder / file | What it is | Related video |
|---------------|------------|---------------|
| [`cli_tool/`](cli_tool/) | `aireview`: a terminal git diff reviewer. Sends `git diff` to a local Ollama model, validates the output with Pydantic, and prints it with Rich. Includes prompts, a chain, and a commit message writer. Packaged for PyPI as `ari-by-harjas-aireview`. | #4, #5 |
| [`cli_tool/GUIDE.md`](cli_tool/GUIDE.md) | Beginner guide to what a Python package is, how this one is built, and how it reached PyPI. | #5 |
| [`cli_tool/dist/`](cli_tool/dist/) | Built wheel and source distribution for version 0.1.0. | #5 |
| [`working_with_llms/`](working_with_llms/) | Hands-on demo: running a model locally with Ollama, calling Gemini, and building a tool-calling agent with LangChain. Includes a Jupyter notebook, a landing page (`index.html`), and `.env.example` for the Gemini key. | #3 |
| [`llm_training/llm_training_notebook.html`](llm_training/llm_training_notebook.html) | HTML notebook covering the LLM training lifecycle: pre-training and post-training. | #6 |
| [`llm_training/`](llm_training/) | Continual pretraining (CPT) and QLoRA instruction tuning on Ubuntu documentation. Includes the notebook (`CPT+SFT.ipynb`), five cleaned domain corpus files (`domain_corpus/`), and a 1,412-line instruction dataset (`instruction_dataset.jsonl`). | #7 |

## Setup notes

- Python 3.10+ is needed for the demos.
- `cli_tool/` needs [Ollama](https://ollama.com) running locally with `llama3.1:8b` pulled.
- `working_with_llms/` needs a free Gemini API key. Copy `.env.example` to `.env` and add your key. Do not commit `.env`.
