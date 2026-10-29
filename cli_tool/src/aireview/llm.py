"""Chapter 2: talk to the local model and force it to follow a schema."""
from importlib.resources import files
from typing import TypeVar

import httpx
import ollama
from pydantic import BaseModel, ValidationError

from .config import NUM_CTX, NUM_PREDICT, REQUEST_TIMEOUT
from .schema import CommitMessage, FixPlan, Finding, ReviewResult

PROMPTS = files("aireview") / "prompts"  # prompts ship inside the package as plain .md files


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8").strip()


T = TypeVar("T", bound=BaseModel)

OPTIONS = {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT}  # explicit: Ollama's defaults are smaller
_client = ollama.Client(timeout=REQUEST_TIMEOUT)
TRACE: list[dict] = []  # one entry per model call; read by `aireview --trace`


class LLMError(Exception):
    pass


def check_model(model: str) -> None:
    """Fail fast if Ollama is not running or the model is not pulled."""
    try:
        names = {m.model for m in _client.list().models}
    except Exception:
        raise LLMError("cannot reach Ollama - is it running? (try: ollama serve)")
    if model not in names and f"{model}:latest" not in names:
        raise LLMError(f"model '{model}' not found - run: ollama pull {model}")


def ask(schema: type[T], system: str, user: str, model: str, step: str = "llm", retries: int = 1) -> T:
    """One structured LLM call: prompt in, validated Pydantic object out. Every chain step uses this."""
    last_error: Exception | None = None
    for _ in range(retries + 1):
        try:
            response = _client.chat(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                format=schema.model_json_schema(),  # structured output
                options=OPTIONS,
            )
            TRACE.append({
                "step": step, "model": model, "schema": schema.__name__, "options": OPTIONS,
                "system_prompt": system, "user_prompt": user, "raw_response": response.message.content,
                "prompt_tokens": getattr(response, "prompt_eval_count", None),
                "output_tokens": getattr(response, "eval_count", None),
                "done_reason": getattr(response, "done_reason", None),  # "length" = hit num_predict
                "seconds": round((getattr(response, "total_duration", 0) or 0) / 1e9, 2),
            })
            return schema.model_validate_json(response.message.content)
        except ValidationError as e:
            last_error = e
        except httpx.TimeoutException:
            raise LLMError(f"{step}: model did not answer within {REQUEST_TIMEOUT}s")
        except Exception as e:
            raise LLMError(f"model call failed: {e}")
    raise LLMError(f"model returned invalid output after {retries + 1} attempts: {last_error}")


def review_diff(diff: str, model: str) -> ReviewResult:
    return ask(ReviewResult, load_prompt("review"), f"Review this diff:\n\n{diff}", model, step="1 review")


def advise_fixes(diff: str, findings: list[Finding], model: str) -> FixPlan:
    listing = "\n".join(f"- [{f.severity}] {f.file}: {f.issue}" for f in findings)
    return ask(FixPlan, load_prompt("fix_advisor"), f"Findings:\n{listing}\n\nDiff:\n{diff}", model, step="2 fix advisor")


def write_commit_message(diff: str, review: ReviewResult, model: str) -> CommitMessage:
    context = f"Change type: {review.commit_type}\nBreaking: {review.breaking_change}\n\nDiff:\n{diff}"
    return ask(CommitMessage, load_prompt("commit_writer"), context, model, step="3 commit writer")
