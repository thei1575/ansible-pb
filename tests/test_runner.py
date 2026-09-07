"""Command quoting, recap parsing and the pty streamer."""

from __future__ import annotations

from pathlib import Path

from pb import runner

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
    lines: list[str] = []
    code = runner.stream(
        ["sh", "-c", "echo one; echo two; exit 4"],
        tmp_path,
        lines.append,
        lambda: False,
    )
    assert code == 4
    assert [runner.strip_ansi(x).strip() for x in lines if x.strip()] == ["one", "two"]


def test_stream_runs_in_the_given_directory(tmp_path: Path) -> None:
    lines: list[str] = []
    runner.stream(["pwd"], tmp_path, lines.append, lambda: False)
    assert str(tmp_path.resolve()) in "".join(lines)


def test_stream_reports_a_missing_binary_instead_of_raising(tmp_path: Path) -> None:
    lines: list[str] = []
    code = runner.stream(["pb-does-not-exist"], tmp_path, lines.append, lambda: False)
    assert code == 127
    assert "not found on PATH" in "".join(lines)


def test_stream_allocates_a_tty_so_ansible_keeps_its_colour(tmp_path: Path) -> None:
    lines: list[str] = []
    code = runner.stream(
        ["sh", "-c", "test -t 1 && echo tty || echo pipe"],
        tmp_path,
        lines.append,
        lambda: False,
    )
    assert code == 0
    assert "tty" in "".join(lines)


def test_stream_stops_when_cancelled(tmp_path: Path) -> None:
    """Cancelling must kill the process group, not leave it running."""
    lines: list[str] = []
    code = runner.stream(
        ["sh", "-c", "echo started; sleep 30"],
        tmp_path,
        lines.append,
        lambda: True,
        cols=80,
    )
    assert code != 0
