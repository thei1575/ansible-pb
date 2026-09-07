"""Run ansible as a child process and stream its output back line by line.

The child gets a pty rather than a pipe: ansible only emits colour when it
believes it is talking to a terminal, and the whole point of this tool is to
look at that output. The child also gets its own process group so that
cancelling kills the forks ansible spawned, not just ansible itself.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import os
import pty
import re
import select
import shlex
import signal
import struct
import subprocess
import termios
from collections.abc import Callable, Mapping
from pathlib import Path

# ansible prints a recap line per host: "web01 : ok=12 changed=3 ..."
RECAP_KEYS = ("ok", "changed", "unreachable", "failed", "skipped", "rescued", "ignored")


def quote(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)


def _set_size(fd: int, cols: int, rows: int) -> None:
    with contextlib.suppress(OSError):
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def stream(
    argv: list[str],
    cwd: Path,
    on_line: Callable[[str], None],
    cancelled: Callable[[], bool],
    cols: int = 120,
    rows: int = 50,
    extra_env: Mapping[str, str] | None = None,
) -> int:
    """Run `argv`, calling `on_line` for each line of output. Returns the exit code.

    `cancelled` is polled a few times a second; when it turns true the child's
    whole process group is terminated. `extra_env` is merged in last, so a
    plugin may set ANSIBLE_* variables for this run - but not unset the pty
    settings the reader below depends on.
    """
    master, slave = pty.openpty()
    _set_size(slave, cols, rows)
    env = {
        **os.environ,
        **(extra_env or {}),
        "ANSIBLE_FORCE_COLOR": "1",
        "PY_COLORS": "1",
        "TERM": "xterm-256color",
        "COLUMNS": str(cols),
        # Nothing here is interactive; a prompt would deadlock the pty reader.
        "ANSIBLE_NOCOWS": "1",
    }

    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
            start_new_session=True,
        )
    except FileNotFoundError:
        os.close(master)
        os.close(slave)
        on_line(f"pb: {argv[0]}: not found on PATH")
        return 127

    # The parent holds the slave open on purpose, for the length of the read
    # loop. Closing it here makes the master report EOF the moment the child
    # exits, and on BSD that EOF discards whatever is still sitting in the pty
    # buffer - which is where the last lines of a run live, PLAY RECAP
    # included. A short command can lose its output entirely that way.
    #
    # With a writer still open no EOF arrives, so the loop below ends the way
    # it was always written to: the child is gone and the buffer has drained.
    killed = False
    buf = b""
    try:
        while True:
            if cancelled() and not killed:
                killed = True
                on_line("\n\x1b[33m-- cancelled, terminating --\x1b[0m")
                _signal_group(proc, signal.SIGTERM)

            try:
                ready, _, _ = select.select([master], [], [], 0.15)
            except (OSError, ValueError):
                break
            if not ready:
                # Child is gone and the pty has nothing left. `_drain_ready` is
                # what gives a dying child the chance to flush its last lines,
                # so this holds for a cancelled run too - and it has to, since
                # the parent keeps a writer open and no EOF is ever coming.
                if proc.poll() is not None and not _drain_ready(master):
                    break
                continue

            try:
                data = os.read(master, 65536)
            except OSError as exc:
                # Linux raises EIO at EOF on a pty; macOS just returns b"".
                if exc.errno != errno.EIO:
                    raise
                data = b""
            if not data:
                break

            buf += data
            *lines, buf = buf.split(b"\n")
            for line in lines:
                on_line(line.decode("utf-8", "replace").rstrip("\r"))
    finally:
        for fd in (master, slave):
            with contextlib.suppress(OSError):
                os.close(fd)

    if buf:
        on_line(buf.decode("utf-8", "replace").rstrip("\r"))

    try:
        code = proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _signal_group(proc, signal.SIGKILL)
        code = proc.wait()
    return code


def _drain_ready(fd: int) -> bool:
    ready, _, _ = select.select([fd], [], [], 0)
    return bool(ready)


def _signal_group(proc: subprocess.Popen, sig: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(proc.pid), sig)


def parse_recap(lines: list[str]) -> dict[str, dict[str, int]]:
    """Pull the per-host counters out of a PLAY RECAP block."""
    recap: dict[str, dict[str, int]] = {}
    seen_header = False
    for raw in lines:
        line = strip_ansi(raw).strip()
        if "PLAY RECAP" in line:
            seen_header = True
            continue
        if not seen_header or ":" not in line:
            continue
        host, _, rest = line.partition(":")
        counts = {}
        for key in RECAP_KEYS:
            match = _count(rest, key)
            if match is not None:
                counts[key] = match
        if counts:
            recap[host.strip()] = counts
    return recap


def _count(text: str, key: str) -> int | None:
    marker = f"{key}="
    idx = text.find(marker)
    if idx < 0:
        return None
    digits = ""
    for ch in text[idx + len(marker):]:
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)
