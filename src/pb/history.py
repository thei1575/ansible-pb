"""A durable record of everything pb has run.

Infra work needs an answer to "what did I apply, when, against which commit,
and did it work". The log scrolls away; this does not. Records live under
.pb/runs/ (gitignored) as a JSON sidecar plus the captured output.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import meta

KEEP = 300  # prune beyond this many records


@dataclass
class Run:
    id: str
    label: str
    argv: list[str]
    started: float
    duration: float
    exit_code: int
    recap: dict = field(default_factory=dict)
    git_sha: str = ""
    git_branch: str = ""
    git_dirty: int = 0
    hosts: list[str] = field(default_factory=list)

    @property
    def when(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.started))

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def applied(self) -> bool:
        """True for a real apply, as opposed to a check or syntax run."""
        return not any(a in self.argv for a in ("--check", "--syntax-check", "--list-hosts"))

    def recap_summary(self) -> str:
        totals: dict[str, int] = {}
        for counts in self.recap.values():
            for key, value in counts.items():
                totals[key] = totals.get(key, 0) + value
        parts = [f"{k}={totals[k]}" for k in ("ok", "changed", "failed", "unreachable")
                 if totals.get(k)]
        return " ".join(parts)


def runs_dir(repo: meta.Repo) -> Path:
    return repo.root / ".pb" / "runs"


def record(
    repo: meta.Repo,
    label: str,
    argv: list[str],
    started: float,
    exit_code: int,
    lines: list[str],
    recap: dict,
) -> Run | None:
    """Persist one run. Never raises: losing history must not kill a run."""
    from . import runner

    try:
        directory = runs_dir(repo)
        directory.mkdir(parents=True, exist_ok=True)
        run_id = time.strftime("%Y%m%d-%H%M%S", time.localtime(started))
        branch, dirty = meta.git_status(repo)
        code, sha = meta.capture(["git", "rev-parse", "--short", "HEAD"], repo.root, timeout=10)
        run = Run(
            id=run_id,
            label=label,
            argv=argv,
            started=started,
            duration=time.time() - started,
            exit_code=exit_code,
            recap=recap,
            git_sha=sha.strip() if code == 0 else "",
            git_branch=branch,
            git_dirty=dirty,
            hosts=sorted(recap),
        )
        (directory / f"{run_id}.log").write_text(
            "\n".join(runner.strip_ansi(line) for line in lines) + "\n"
        )
        (directory / f"{run_id}.json").write_text(json.dumps(asdict(run), indent=2))
        _prune(directory)
        return run
    except OSError:
        return None


def _prune(directory: Path) -> None:
    records = sorted(directory.glob("*.json"), reverse=True)
    for stale in records[KEEP:]:
        stale.unlink(missing_ok=True)
        stale.with_suffix(".log").unlink(missing_ok=True)


def load(repo: meta.Repo) -> list[Run]:
    """Every recorded run, newest first. Skips anything unreadable."""
    directory = runs_dir(repo)
    if not directory.is_dir():
        return []
    runs: list[Run] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text())
            runs.append(Run(**data))
        except (OSError, ValueError, TypeError):
            continue
    return runs


def log_for(repo: meta.Repo, run: Run) -> str:
    path = runs_dir(repo) / f"{run.id}.log"
    try:
        return path.read_text()
    except OSError:
        return "(log missing)"
