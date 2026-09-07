"""Command quoting, recap parsing and the pty streamer."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from pb import runner


def _stream(argv: list[str], cwd: Path, cancelled=lambda: False, timeout: float = 20.0):
    """Run `stream` on a thread so a hang fails the test instead of the suite.

    The read loop ends on `proc.poll()` plus an empty pty rather than on EOF,
    and getting that condition wrong wedges it forever. That must never be
    something CI discovers by timing out.
    """
    lines: list[str] = []
    result: list[int] = []
    thread = threading.Thread(
        target=lambda: result.append(runner.stream(argv, cwd, lines.append, cancelled)),
        daemon=True,
    )
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        pytest.fail(f"stream({argv}) did not return within {timeout}s — it hung")
    return result[0], lines

# Real `ansible-playbook` output, with the banner rules and column padding
# trimmed to fit. parse_recap must not care about either.
RECAP = """\
PLAY [Web servers] ****************************

TASK [nginx : install] ************************
ok: [web01]

PLAY RECAP ************************************
web01     : ok=12  changed=3  unreachable=0  failed=0  skipped=1  rescued=0  ignored=0
web02     : ok=11  changed=0  unreachable=0  failed=1  skipped=0  rescued=0  ignored=0
stg01     : ok=0   changed=0  unreachable=1  failed=0  skipped=0  rescued=0  ignored=0
"""


def test_quote_shell_escapes_arguments() -> None:
    assert runner.quote(["ansible-playbook", "site.yml"]) == "ansible-playbook site.yml"
    assert runner.quote(["--limit", "web,db"]) == "--limit web,db"
    assert runner.quote(["-e", "msg=hello world"]) == "-e 'msg=hello world'"
    assert runner.quote(["-e", "x=$(rm -rf /)"]) == "-e 'x=$(rm -rf /)'"


def test_strip_ansi_removes_colour_codes() -> None:
    assert runner.strip_ansi("\x1b[0;32mok: [web01]\x1b[0m") == "ok: [web01]"
    assert runner.strip_ansi("plain") == "plain"


def test_parse_recap_reads_the_counters_per_host() -> None:
    recap = runner.parse_recap(RECAP.splitlines())
    assert set(recap) == {"web01", "web02", "stg01"}
    assert recap["web01"] == {
        "ok": 12,
        "changed": 3,
        "unreachable": 0,
        "failed": 0,
        "skipped": 1,
        "rescued": 0,
        "ignored": 0,
    }
    assert recap["web02"]["failed"] == 1
    assert recap["stg01"]["unreachable"] == 1


def test_parse_recap_ignores_everything_before_the_header() -> None:
    """Task lines contain colons too; only the recap block counts."""
    lines = [
        "TASK [nginx : install] ****",
        "ok: [web01]",
        "PLAY RECAP ****",
        "web01 : ok=1 changed=0",
    ]
    assert runner.parse_recap(lines) == {"web01": {"ok": 1, "changed": 0}}


def test_parse_recap_handles_coloured_output() -> None:
    lines = ["\x1b[0;32mPLAY RECAP ****\x1b[0m", "\x1b[0;33mweb01 : ok=2 changed=1\x1b[0m"]
    assert runner.parse_recap(lines) == {"web01": {"ok": 2, "changed": 1}}


def test_parse_recap_is_empty_without_a_recap() -> None:
    assert runner.parse_recap(["PLAY [x] ***", "fatal: [web01]: UNREACHABLE!"]) == {}
    assert runner.parse_recap([]) == {}


# --- the pty streamer ------------------------------------------------


def test_stream_captures_output_and_the_exit_code(tmp_path: Path) -> None:
    code, lines = _stream(["sh", "-c", "echo one; echo two; exit 4"], tmp_path)
    assert code == 4
    assert [runner.strip_ansi(x).strip() for x in lines if x.strip()] == ["one", "two"]


def test_stream_runs_in_the_given_directory(tmp_path: Path) -> None:
    _, lines = _stream(["pwd"], tmp_path)
    assert str(tmp_path.resolve()) in "".join(lines)


def test_stream_reports_a_missing_binary_instead_of_raising(tmp_path: Path) -> None:
    code, lines = _stream(["pb-does-not-exist"], tmp_path)
    assert code == 127
    assert "not found on PATH" in "".join(lines)


def test_stream_allocates_a_tty_so_ansible_keeps_its_colour(tmp_path: Path) -> None:
    code, lines = _stream(["sh", "-c", "test -t 1 && echo tty || echo pipe"], tmp_path)
    assert code == 0
    assert "tty" in "".join(lines)


def test_stream_stops_when_cancelled(tmp_path: Path) -> None:
    """Cancelling must kill the process group, not leave it running."""
    code, _ = _stream(["sh", "-c", "echo started; sleep 30"], tmp_path, lambda: True)
    assert code != 0


def test_a_cancelled_run_still_returns(tmp_path: Path) -> None:
    """The read loop ends on poll()+drain, not on EOF — including after a kill.

    Getting this wrong loops forever with a writer the parent never closed.
    """
    code, _ = _stream(["sh", "-c", "sleep 30"], tmp_path, lambda: True, timeout=15.0)
    assert code != 0


@pytest.mark.parametrize("run", range(12))
def test_a_command_that_exits_at_once_still_has_its_output(tmp_path: Path, run: int) -> None:
    """The last thing a run prints is PLAY RECAP, so losing the tail is not
    cosmetic. Closing the pty slave in the parent let a BSD EOF discard the
    buffer, and a command this short lost everything — intermittently, which
    is why this runs more than once.
    """
    code, lines = _stream(["sh", "-c", "echo first; echo last"], tmp_path)
    assert code == 0
    assert [runner.strip_ansi(x).strip() for x in lines if x.strip()] == ["first", "last"]


def test_the_final_line_survives_without_a_trailing_newline(tmp_path: Path) -> None:
    code, lines = _stream(["printf", "no trailing newline"], tmp_path)
    assert code == 0
    assert "no trailing newline" in "".join(lines)
