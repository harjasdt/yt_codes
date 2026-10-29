"""Chapter 4: chaining. Each step's typed output feeds the next; plain Python decides the route."""
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from . import llm
from .git_inspector import filter_diff
from .schema import CommitMessage, FixPlan, ReviewResult

SERIOUS = {"high", "critical"}


class ChainResult(BaseModel):
    review: ReviewResult
    fixes: FixPlan | None
    commit: CommitMessage


@dataclass
class Hooks:
    """Callbacks so the chain stays UI-agnostic."""
    start: Callable[[int], None] = lambda i: None
    done: Callable[[int, str], None] = lambda i, detail="": None
    skip: Callable[[int, str], None] = lambda i, reason="": None


# step indexes: 0 review, 1 fixes, 2 commit message
def run_chain(diff: str, model: str, hooks: Hooks = Hooks()) -> ChainResult:
    hooks.start(0)
    review = llm.review_diff(diff, model)                     # LLM call 1: diff -> ReviewResult
    hooks.done(0, f"risk {review.risk_score}/10, {len(review.findings)} findings")

    serious = [f for f in review.findings if f.severity in SERIOUS]
    fixes = None
    if serious:                                               # router: plain Python, not an agent
        hooks.start(1)
        fixes = llm.advise_fixes(filter_diff(diff, {f.file for f in serious}), serious, model)        # LLM call 2: findings -> FixPlan
        hooks.done(1, f"{len(fixes.steps)} steps")
    else:
        hooks.skip(1, "no serious findings")

    hooks.start(2)
    commit = llm.write_commit_message(diff, review, model)    # LLM call 3: diff + review -> CommitMessage
    hooks.done(2, commit.subject)
    return ChainResult(review=review, fixes=fixes, commit=commit)
