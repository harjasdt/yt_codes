"""Chapter 1: the subprocess bridge between Python and git."""
import os
import re
import subprocess
from dataclasses import dataclass, field

from .config import MAX_DIFF_CHARS, MAX_NEW_FILE_BYTES, PER_FILE_CHARS

NOISE_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Pipfile.lock", "Cargo.lock"}
NOISE_SUFFIXES = (".pyc", ".ipynb", ".min.js", ".min.css", ".map", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".svg")
SOURCE = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".c", ".h", ".cpp", ".rb", ".php", ".swift", ".cs", ".sh", ".sql"}
CONFIG = {".toml", ".yaml", ".yml", ".json", ".cfg", ".ini"}
DOCS = {".md", ".rst", ".txt"}

_BINARY = re.compile(r"^Binary files ", re.M)  # git prints this at the start of a line; code lines start with + - or space
_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.M)


class GitError(Exception):
    pass


@dataclass
class DiffInfo:
    text: str
    source: str  # e.g. "staged + unstaged + 2 new"
    files: int
    added: int
    removed: int
    trimmed: list[str] = field(default_factory=list)  # included, but cut to PER_FILE_CHARS
    dropped: list[str] = field(default_factory=list)  # NOT shown to the model: over budget or too large
    ignored: list[str] = field(default_factory=list)  # noise on purpose: lockfiles, binaries, notebooks

    @property
    def partial(self) -> bool:
        """True when the model did not see everything that changed."""
        return bool(self.trimmed or self.dropped)


def _git(root: str, *args: str) -> str:
    try:
        result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=root)
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH")
    if result.returncode != 0:
        raise GitError(result.stderr.strip())
    return result.stdout


def _repo_root() -> str:
    # outside a repo `git diff` silently switches to --no-index mode, so check first
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH")
    if r.returncode != 0:
        raise GitError("not a git repository")
    return r.stdout.strip()


def split_diff(text: str) -> list[tuple[str, str]]:
    """Split one big diff into (path, that file's diff) pairs."""
    heads = list(_HEADER.finditer(text))
    return [(m.group(2), text[m.start(): heads[i + 1].start() if i + 1 < len(heads) else len(text)])
            for i, m in enumerate(heads)]


def filter_diff(text: str, files: set[str]) -> str:
    """Keep only the diffs of the named files (falls back to everything if none match)."""
    kept = [chunk for path, chunk in split_diff(text)
            if any(path == f or path.endswith("/" + f) or f.endswith("/" + path) for f in files)]
    return "".join(kept) or text


def _priority(path: str) -> int:
    ext = os.path.splitext(path)[1].lower()
    return 0 if ext in SOURCE else 1 if ext in CONFIG else 3 if ext in DOCS else 2


def _is_noise(path: str, chunk: str) -> bool:
    return (os.path.basename(path) in NOISE_NAMES or path.lower().endswith(NOISE_SUFFIXES)
            or _BINARY.search(chunk) is not None)


def _untracked(root: str) -> tuple[list[tuple[str, str]], list[str]]:
    """New files git does not track yet never show up in `git diff`, so diff each one against /dev/null."""
    chunks, too_big = [], []
    for name in _git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        try:
            if os.path.getsize(os.path.join(root, name)) > MAX_NEW_FILE_BYTES:
                too_big.append(name)
                continue
        except OSError:
            continue
        # exit code 1 just means "files differ", so do not use the _git helper here
        out = subprocess.run(["git", "diff", "--no-index", "--", os.devnull, name],
                             capture_output=True, text=True, cwd=root).stdout
        chunks.extend(split_diff(out))
    return chunks, too_big


def get_diff(staged_only: bool = False) -> DiffInfo:
    root = _repo_root()  # every git call runs from the repo root, so tracked and new files are scoped the same way
    chunks: list[tuple[str, str]] = []
    labels: list[str] = []
    dropped: list[str] = []
    oversize = 0

    staged = split_diff(_git(root, "diff", "--staged"))
    if staged:
        chunks += staged
        labels.append("staged")
    if not staged_only:  # default: review everything you changed, not just what is staged
        unstaged = split_diff(_git(root, "diff"))
        if unstaged:
            chunks += unstaged
            labels.append("unstaged")
        new, too_big = _untracked(root)
        if new or too_big:
            chunks += new
            dropped += too_big
            oversize = len(too_big)
            labels.append(f"{len(new) + len(too_big)} new")
    if not chunks and not dropped:
        raise GitError("no staged changes found" if staged_only else "no changes found (staged, unstaged or new files)")

    kept, trimmed, ignored = [], [], []
    added = removed = used = 0
    for path, chunk in sorted(chunks, key=lambda pc: _priority(pc[0])):  # code first, docs last
        if _is_noise(path, chunk):
            ignored.append(path)
            continue
        lines = chunk.splitlines()
        added += sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        removed += sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        if used >= MAX_DIFF_CHARS:
            dropped.append(path)
            continue
        if len(chunk) > PER_FILE_CHARS:
            chunk = chunk[:PER_FILE_CHARS] + "\n... [file truncated]\n"
            trimmed.append(path)
        kept.append(chunk)
        used += len(chunk)

    if not kept:
        raise GitError(f"only ignored files changed ({', '.join(ignored[:3])}...)" if ignored else "nothing reviewable changed")
    return DiffInfo("".join(kept), " + ".join(labels), len(chunks) + oversize, added, removed, trimmed, dropped, ignored)
