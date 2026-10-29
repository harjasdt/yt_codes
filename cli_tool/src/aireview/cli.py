"""Orchestrator: plain sequential calls, no agent loop. git -> llm -> schema -> render."""
import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from . import __version__, ui
from .git_inspector import GitError, get_diff
from .chain import Hooks, run_chain
from . import llm
from .llm import LLMError, check_model

app = typer.Typer(add_completion=False, help="Review your git changes with a local LLM.")


def _detail(diff) -> str:
    text = f"{diff.source}: {diff.files} files, +{diff.added} -{diff.removed}"
    bits = [f"{len(v)} {name}" for v, name in ((diff.trimmed, "trimmed"), (diff.dropped, "not reviewed"), (diff.ignored, "ignored")) if v]
    return text + (f" ({', '.join(bits)})" if bits else "")


def _emit_trace(show: bool, path: Optional[Path], to_stderr: bool = False) -> None:
    if path:
        path.write_text(json.dumps(llm.TRACE, indent=2))
    if show and llm.TRACE:
        ui.show_trace(llm.TRACE, ui.Console(stderr=True) if to_stderr else ui.console)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"aireview {__version__}")
        raise typer.Exit()


@app.command()
def main(
    model: Annotated[str, typer.Option("--model", "-m", help="Ollama model to use")] = "llama3.1:8b",
    staged_only: Annotated[bool, typer.Option("--staged-only", help="Review only staged changes (default: staged + unstaged + new files)")] = False,
    no_anim: Annotated[bool, typer.Option("--no-anim", help="Skip the startup animation")] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Print the validated result as JSON only")] = False,
    fail_on_risk: Annotated[Optional[int], typer.Option("--fail-on-risk", help="Exit 2 if risk >= N")] = None,
    trace: Annotated[bool, typer.Option("--trace", help="Print every LLM call: prompts, options, raw reply, tokens, time")] = False,
    trace_file: Annotated[Optional[Path], typer.Option("--trace-file", help="Save the full trace as JSON")] = None,
    version: Annotated[Optional[bool], typer.Option("--version", callback=_version, is_eager=True)] = None,
) -> None:
    if json_out:  # machine mode: no banner, no live UI
        try:
            diff = get_diff(staged_only)
            result = run_chain(diff.text, model)
        except (GitError, LLMError) as e:
            typer.echo(f"error: {e}", err=True)
            _emit_trace(trace, trace_file, to_stderr=True)
            raise typer.Exit(1)
        if diff.partial:
            typer.echo(f"warning: partial review ({_detail(diff)})", err=True)
        typer.echo(result.model_dump_json(indent=2))
        _emit_trace(trace, trace_file, to_stderr=True)
        raise typer.Exit(2 if fail_on_risk and result.review.risk_score >= fail_on_risk else 0)

    ui.show_banner(model, animate=ui.console.is_terminal and not no_anim)

    steps = ["Inspecting git changes", f"Connecting to Ollama ({model})",
             "1/3 Reviewing diff", "2/3 Planning fixes", "3/3 Writing commit message"]
    current = 0
    with ui.Pipeline(steps) as p:
        try:
            p.start(0)
            diff = get_diff(staged_only)
            p.done(0, _detail(diff))

            current = 1
            p.start(1)
            check_model(model)
            p.done(1)

            # chain step i is pipeline row i + 2
            hooks = Hooks(
                start=lambda i: p.start(i + 2),
                done=lambda i, detail="": p.done(i + 2, detail),
                skip=lambda i, reason="": p.skip(i + 2, reason),
            )
            current = 2
            result = run_chain(diff.text, model, hooks)
        except (GitError, LLMError) as e:
            p.fail(next((i for i, st in enumerate(p.state) if st == "running"), current), str(e))
            _emit_trace(False, trace_file)
            raise typer.Exit(1)

    ui.console.print()
    ui.show_result(result, partial=diff.partial)
    if diff.partial:
        ui.show_partial_warning(diff)
    _emit_trace(trace, trace_file)
    if fail_on_risk and result.review.risk_score >= fail_on_risk:
        raise typer.Exit(2)
