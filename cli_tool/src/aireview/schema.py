"""Chapter 3: the contract. LLM output becomes a typed Python object."""
from typing import Literal

from pydantic import BaseModel, Field


class Finding(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    file: str = Field(description="File path the finding refers to")
    issue: str = Field(description="What is wrong or risky")
    suggestion: str = Field(description="Concrete fix or improvement")


class ReviewResult(BaseModel):
    commit_type: Literal["feat", "fix", "refactor", "docs", "test", "chore", "perf", "style"]
    summary: str = Field(max_length=50, description="Commit-style summary, 50 characters max")
    breaking_change: bool
    risk_score: int = Field(ge=1, le=10, description="1 = trivial, 10 = dangerous")
    findings: list[Finding]


class FixStep(BaseModel):
    file: str
    problem: str = Field(description="The issue being fixed, in one sentence")
    fix: str = Field(description="Short, code-level instruction for the fix")


class FixPlan(BaseModel):
    steps: list[FixStep]


class CommitMessage(BaseModel):
    subject: str = Field(max_length=50, description="Conventional commit subject, e.g. 'fix: parameterize user query'")
    body: list[str] = Field(description="Short bullet lines describing what changed and why")
