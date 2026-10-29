"""Chapter 4: all terminal presentation lives here. Run once, animate, print, exit."""
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from . import __version__
from .chain import ChainResult
from .schema import ReviewResult

console = Console()

LOGO = r"""
       _                  _
  __ _(_)_ __ _____   _(_) _____      __
 / _` | | '__/ _ \ \ / / |/ _ \ \ /\ / /
| (_| | | | |  __/\ V /| |  __/\ V  V /
 \__,_|_|_|  \___| \_/ |_|\___| \_/\_/
""".strip("\n").splitlines()

GRADIENT = ["#7aa2f7", "#7dcfff", "#2ac3de", "#9ece6a", "#bb9af7"]
SEVERITY_STYLE = {"low": "green", "medium": "yellow", "high": "red", "critical": "bold white on red"}


def _risk_style(result: ReviewResult) -> str:
    if result.breaking_change or result.risk_score >= 7:
        return "red"
    return "yellow" if result.risk_score >= 4 else "green"


def show_banner(model: str, animate: bool) -> None:
    tagline = f"local AI diff review  ·  v{__version__}  ·  {model}"
    if not animate:
        console.print(Text("\n".join(LOGO), style="bold cyan"))
        console.print(Text(tagline, style="dim"), "\n")
        return

    shown: list[Text] = []
    with Live(console=console, refresh_per_second=30, transient=False) as live:
        for i, line in enumerate(LOGO):  # reveal row by row, diagonal colour sweep
            width = max(len(l) for l in LOGO)
            for col in range(0, width + 4, 4):
                row = Text()
                for c, ch in enumerate(line):
                    if c < col:
                        row.append(ch, style=f"bold {GRADIENT[(c // 8 + i) % len(GRADIENT)]}")
                live.update(Group(*shown, row))
                time.sleep(0.008)
            shown.append(row)
        typed = ""
        for ch in tagline:  # typewriter tagline
            typed += ch
            live.update(Group(*shown, Text(typed + "▌", style="dim")))
            time.sleep(0.012)
        live.update(Group(*shown, Text(tagline, style="dim")))
    console.print()


class Pipeline:
    """Live checklist: pending -> spinner -> ✔ / ✖, with elapsed time per step."""

    def __init__(self, steps: list[str]):
        self.labels = steps
        self.state = ["pending"] * len(steps)
        self.detail = [""] * len(steps)
        self.elapsed = [0.0] * len(steps)
        self._started = [0.0] * len(steps)
        self.live = Live(self, console=console, refresh_per_second=15)

    def __rich__(self) -> Group:
        rows = []
        for i, label in enumerate(self.labels):
            if self.state[i] == "running":
                t = time.monotonic() - self._started[i]
                icon = Spinner("dots", text=Text(f" {label}  {t:.1f}s", style="cyan"))
                rows.append(icon)
                continue
            mark, style = {"pending": ("○", "dim"), "done": ("✔", "green"), "failed": ("✖", "bold red"), "skipped": ("–", "dim")}[self.state[i]]
            line = Text(f"{mark} {label}", style=style)
            if self.state[i] != "pending":
                line.append(f"  {self.elapsed[i]:.1f}s", style="dim")
            if self.detail[i]:
                line.append(f"  {self.detail[i]}", style="red" if self.state[i] == "failed" else "dim")
            rows.append(line)
        return Group(*rows)

    def __enter__(self):
        self.live.start()
        return self

    def __exit__(self, *exc):
        self.live.stop()

    def start(self, i: int) -> None:
        self.state[i], self._started[i] = "running", time.monotonic()

    def done(self, i: int, detail: str = "") -> None:
        self.state[i], self.detail[i] = "done", detail
        self.elapsed[i] = time.monotonic() - self._started[i]

    def skip(self, i: int, reason: str = "") -> None:
        self.state[i], self.detail[i] = "skipped", reason

    def fail(self, i: int, reason: str) -> None:
        self.state[i], self.detail[i] = "failed", reason
        self.elapsed[i] = time.monotonic() - self._started[i]


def show_result(chain: ChainResult, partial: bool = False) -> None:
    result = chain.review
    style = _risk_style(result)
    bar = "█" * result.risk_score + "░" * (10 - result.risk_score)

    meta = Table.grid(padding=(0, 2))
    meta.add_row("Type", Text(result.commit_type, style="bold cyan"))
    meta.add_row("Risk", Text(f"{bar} {result.risk_score}/10", style=style))
    meta.add_row(
        "Breaking",
        Text("YES" if result.breaking_change else "no", style="bold red" if result.breaking_change else "green"),
    )

    body: list = [meta, Text()]
    if result.findings:
        table = Table(show_header=True, header_style="bold", expand=True, box=None, padding=(0, 1))
        table.add_column("Severity", no_wrap=True)
        table.add_column("File", style="cyan")
        table.add_column("Issue / Suggestion")
        for f in result.findings:
            detail = Text(f.issue)
            detail.append(f"\n→ {f.suggestion}", style="dim")
            table.add_row(Text(f.severity.upper(), style=SEVERITY_STYLE[f.severity]), f.file, detail)
        body.append(table)
    else:
        body.append(Text("No issues found in the part of the diff the model saw (partial review)." if partial
                         else "✔ No issues found in this diff.", style="yellow" if partial else "green"))

    console.print(
        Panel(
            Group(*body),
            title=f"[bold]{result.commit_type}: {result.summary}[/bold]",
            border_style=style,
            padding=(1, 2),
        )
    )

    if chain.fixes:
        fixes = Table(title="Suggested fixes", title_justify="left", box=None, expand=True, padding=(0, 1))
        fixes.add_column("File", style="cyan", no_wrap=True)
        fixes.add_column("Fix")
        for step in chain.fixes.steps:
            fixes.add_row(step.file, Text(f"{step.problem}\n→ {step.fix}"))
        console.print(Panel(fixes, border_style="cyan", padding=(1, 2)))

    message = Text(chain.commit.subject, style="bold green")
    for line in chain.commit.body:
        message.append(f"\n- {line.lstrip('- ')}", style="white")
    console.print(Panel(message, title="Suggested commit message", border_style="green", padding=(1, 2)))


def show_trace(trace: list[dict], out: Console = console, max_chars: int = 1500) -> None:
    """Print every LLM call: exact prompts, options, raw reply, tokens, time."""
    out.print()
    out.rule("[bold]Trace[/bold]  ·  every LLM call", style="cyan")
    for t in trace:
        head = Text(f"{t['step']}  ·  {t['model']}  ·  schema={t['schema']}", style="bold cyan")
        stats = Text(
            f"options={t['options']}  prompt_tokens={t['prompt_tokens']}  "
            f"output_tokens={t['output_tokens']}  time={t['seconds']}s", style="dim")
        user = t["user_prompt"]
        if len(user) > max_chars:  # the diff can be huge; the full text is in --trace-file
            user = user[:max_chars] + f"\n... [{len(t['user_prompt']) - max_chars} more chars, see --trace-file]"
        body = Group(
            head, stats, Text(),
            Text("SYSTEM PROMPT", style="bold yellow"), Text(t["system_prompt"]), Text(),
            Text("USER PROMPT", style="bold yellow"), Text(user), Text(),
            Text("RAW RESPONSE", style="bold yellow"), Text(t["raw_response"]),
        )
        out.print(Panel(body, border_style="cyan", padding=(1, 2)))


def show_partial_warning(info) -> None:
    lines = [Text("⚠ Partial review: the model did not see everything that changed.", style="bold yellow")]
    if info.trimmed:
        lines.append(Text(f"  trimmed to excerpts ({len(info.trimmed)}): {', '.join(info.trimmed[:4])}", style="yellow"))
    if info.dropped:
        lines.append(Text(f"  not reviewed ({len(info.dropped)}): {', '.join(info.dropped[:4])}"
                          + (" ..." if len(info.dropped) > 4 else ""), style="yellow"))
    lines.append(Text("  Review in smaller batches with --staged-only, or stage fewer files.", style="dim"))
    console.print(Panel(Group(*lines), border_style="yellow", padding=(0, 2)))
