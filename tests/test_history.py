"""The durable record under .pb/runs/."""

from __future__ import annotations

import json
import time
from pathlib import Path

from pb import history, meta

RECAP = {
    "web01": {"ok": 10, "changed": 2, "failed": 0, "unreachable": 0},
    "web02": {"ok": 9, "changed": 1, "failed": 1, "unreachable": 0},
}


def _run(**kw: object) -> history.Run:
    base = dict(
        id="20260907-101500",
        label="site.yml",
        argv=["ansible-playbook", "playbooks/site.yml"],
        started=time.time(),
        duration=12.5,
        exit_code=0,
    )
    base.update(kw)
    return history.Run(**base)  # type: ignore[arg-type]


# --- the record itself -----------------------------------------------


def test_ok_follows_the_exit_code() -> None:
    assert _run(exit_code=0).ok
    assert not _run(exit_code=2).ok


def test_applied_is_false_for_a_check_or_syntax_run() -> None:
    argv = ["ansible-playbook", "playbooks/site.yml"]
    assert _run(argv=argv).applied
    assert not _run(argv=[*argv, "--check"]).applied
    assert not _run(argv=[*argv, "--syntax-check"]).applied
    assert not _run(argv=[*argv, "--list-hosts"]).applied


def test_recap_summary_totals_across_hosts_and_drops_zeroes() -> None:
    assert _run(recap=RECAP).recap_summary() == "ok=19 changed=3 failed=1"


def test_recap_summary_is_empty_without_a_recap() -> None:
    assert _run(recap={}).recap_summary() == ""


def test_when_formats_the_start_time_locally() -> None:
    started = time.mktime((2026, 9, 7, 10, 15, 0, 0, 0, -1))
    assert _run(started=started).when == "2026-09-07 10:15"


# --- writing and reading back ----------------------------------------


def test_record_writes_a_json_sidecar_and_a_log(repo: meta.Repo) -> None:
    run = history.record(
        repo,
        label="site.yml",
        argv=["ansible-playbook", "playbooks/site.yml"],
        started=time.time(),
        exit_code=0,
        lines=["\x1b[0;32mok: [web01]\x1b[0m", "PLAY RECAP ****"],
        recap=RECAP,
    )
    assert run is not None
    directory = history.runs_dir(repo)
    assert (directory / f"{run.id}.json").is_file()
    assert (directory / f"{run.id}.log").is_file()
    assert run.hosts == ["web01", "web02"]


def test_the_saved_log_has_no_ansi_escapes(repo: meta.Repo) -> None:
    run = history.record(
        repo, "x", ["true"], time.time(), 0, ["\x1b[0;32mok: [web01]\x1b[0m"], {}
    )
    assert run is not None
    assert history.log_for(repo, run) == "ok: [web01]\n"


def test_record_notes_the_commit_it_ran_against(git_repo: meta.Repo) -> None:
    run = history.record(git_repo, "x", ["true"], time.time(), 0, ["out"], {})
    assert run is not None
    assert len(run.git_sha) >= 7
    assert run.git_branch == "main"
    assert run.git_dirty == 1


def test_record_leaves_git_fields_empty_outside_a_repo(repo: meta.Repo) -> None:
    run = history.record(repo, "x", ["true"], time.time(), 0, ["out"], {})
    assert run is not None
    assert run.git_sha == ""
    assert run.git_branch == ""


def test_load_returns_runs_newest_first(repo: meta.Repo) -> None:
    directory = history.runs_dir(repo)
    directory.mkdir(parents=True)
    for run_id in ("20260101-000000", "20260301-000000", "20260201-000000"):
        (directory / f"{run_id}.json").write_text(
            json.dumps(
                {
                    "id": run_id,
                    "label": "site.yml",
                    "argv": ["true"],
                    "started": 0.0,
                    "duration": 1.0,
                    "exit_code": 0,
                }
            )
        )
    assert [r.id for r in history.load(repo)] == [
        "20260301-000000",
        "20260201-000000",
        "20260101-000000",
    ]


def test_load_is_empty_when_nothing_has_run(repo: meta.Repo) -> None:
    assert history.load(repo) == []


def test_load_skips_an_unreadable_record_rather_than_failing(repo: meta.Repo) -> None:
    """One corrupt sidecar must not hide the rest of the history."""
    good = history.record(repo, "good", ["true"], time.time(), 0, ["out"], {})
    assert good is not None
    directory = history.runs_dir(repo)
    (directory / "20250101-000000.json").write_text("{not json")
    (directory / "20250102-000000.json").write_text('{"id": "x", "unexpected": 1}')
    assert [r.label for r in history.load(repo)] == ["good"]


def test_record_prunes_beyond_the_keep_limit(repo: meta.Repo, monkeypatch) -> None:
    monkeypatch.setattr(history, "KEEP", 3)
    directory = history.runs_dir(repo)
    directory.mkdir(parents=True)
    for n in range(5):
        run_id = f"2025010{n}-000000"
        (directory / f"{run_id}.json").write_text('{"id": "x"}')
        (directory / f"{run_id}.log").write_text("old")
    history.record(repo, "new", ["true"], time.time(), 0, ["out"], {})
    assert len(list(directory.glob("*.json"))) == 3
    # The pruned records take their logs with them.
    assert len(list(directory.glob("*.log"))) == 3


def test_record_returns_none_rather_than_raising_when_it_cannot_write(
    tmp_path: Path, monkeypatch
) -> None:
    """Losing history must never kill a run."""
    repo = meta.Repo.discover(tmp_path / "nope")

    def boom(*_args: object, **_kw: object) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(Path, "mkdir", boom)
    assert history.record(repo, "x", ["true"], time.time(), 0, ["out"], {}) is None


def test_log_for_says_so_when_the_log_is_gone(repo: meta.Repo) -> None:
    assert history.log_for(repo, _run()) == "(log missing)"
