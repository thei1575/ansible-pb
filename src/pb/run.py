"""The full-screen run view: live ansible output with a status line."""

from __future__ import annotations

import time
from collections import deque

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Label, RichLog
from textual.worker import get_current_worker

from . import history, meta, runner


class RunScreen(Screen[int]):
    """Runs one command and streams it. Dismisses with the exit code."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        # `q` is the app-wide quit. Shadow it here: ansible runs in its own
        # process group, so quitting mid-run would leave it applying changes
        # with nothing left to show the output.
        Binding("q", "close", "Close", show=False),
        Binding("ctrl+c", "cancel", "Cancel run", priority=True),
        Binding("w", "wrap", "Wrap"),
        Binding("s", "save", "Save log"),
        Binding("g", "top", "Top"),
        Binding("G", "bottom", "Bottom"),
    ]

    @property
    def running(self) -> bool:
        return self._code is None

    def __init__(self, argv: list[str], repo: meta.Repo, label: str) -> None:
        super().__init__()
        self._argv = argv
        self._repo = repo
        self._cwd = repo.root
        self._label = label
        self._pending: deque[str] = deque()
        self._lines: list[str] = []
        self._cancel = False
        self._started = time.monotonic()
        self._wall_started = time.time()
        self._elapsed: float | None = None   # frozen once the run ends
        self._code: int | None = None

    def compose(self) -> ComposeResult:
        yield Label(f"$ {runner.quote(self._argv)}", id="run-command")
        yield RichLog(highlight=False, markup=False, wrap=False, auto_scroll=True, id="run-log")
        yield Label("", id="run-status")

    def on_mount(self) -> None:
        self.set_interval(0.08, self._drain)
        self.set_interval(0.25, self._tick)
        self._tick()
        self._execute()

    # --- worker ------------------------------------------------------

    @work(thread=True, exclusive=True)
    def _execute(self) -> None:
        worker = get_current_worker()
        width = max(60, self.size.width - 2)
        code = runner.stream(
            self._argv,
            self._cwd,
            self._pending.append,
            lambda: self._cancel or worker.is_cancelled,
            cols=width,
        )
        self._pending.append(f"\x00exit:{code}")

    def _drain(self) -> None:
        log = self.query_one("#run-log", RichLog)
        wrote = False
        while self._pending:
            line = self._pending.popleft()
            if line.startswith("\x00exit:"):
                self._finish(int(line.split(":", 1)[1]))
                continue
            self._lines.append(line)
            log.write(Text.from_ansi(line))
            wrote = True
        if wrote and self._code is None:
            self._tick()

    def _finish(self, code: int) -> None:
        self._code = code
        self._elapsed = time.monotonic() - self._started
        self._tick()
        history.record(
            self._repo,
            self._label,
            self._argv,
            self._wall_started,
            code,
            self._lines,
            runner.parse_recap(self._lines),
        )
        if code != 0:
            self.app.bell()
        self.app.notify(
            f"{self._label} finished with exit code {code}",
            severity="information" if code == 0 else "error",
            timeout=6,
        )

    # --- status line -------------------------------------------------

    def _tick(self) -> None:
        elapsed = (
            self._elapsed if self._elapsed is not None
            else time.monotonic() - self._started
        )
        status = self.query_one("#run-status", Label)
        text = Text()
        if self._code is None:
            spin = "|/-\\"[int(elapsed * 8) % 4]
            text.append(f" {spin} running ", style="bold yellow")
        elif self._code == 0:
            text.append(" ✔ success ", style="bold green")
        else:
            text.append(f" ✘ exit {self._code} ", style="bold red")
        text.append(f" {elapsed:5.1f}s ", style="dim")
        text.append(f" {len(self._lines)} lines ", style="dim")

        recap = runner.parse_recap(self._lines)
        for host, counts in recap.items():
            text.append(f" {host}", style="bold")
            for key, style in (
                ("ok", "green"),
                ("changed", "yellow"),
                ("failed", "red"),
                ("unreachable", "red"),
            ):
                if counts.get(key):
                    text.append(f" {key}={counts[key]}", style=style)
        if self._code is None:
            text.append("   ctrl+c cancels", style="dim")
        else:
            text.append("   esc closes · s saves", style="dim")
        status.update(text)

    # --- actions -----------------------------------------------------

    def action_cancel(self) -> None:
        if self._code is None:
            self._cancel = True
        else:
            self.action_close()

    def action_close(self) -> None:
        if self._code is None:
            self.notify("still running — ctrl+c cancels it first", severity="warning")
            return
        self.dismiss(self._code)

    def action_wrap(self) -> None:
        log = self.query_one("#run-log", RichLog)
        log.wrap = not log.wrap
        log.clear()
        for line in self._lines:
            log.write(Text.from_ansi(line))
        self.notify(f"wrap {'on' if log.wrap else 'off'}")

    def action_top(self) -> None:
        self.query_one("#run-log", RichLog).scroll_home(animate=False)

    def action_bottom(self) -> None:
        self.query_one("#run-log", RichLog).scroll_end(animate=False)

    def action_save(self) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        name = "".join(c if c.isalnum() or c in "-_" else "-" for c in self._label)
        path = self._cwd / f"pb-{name}-{stamp}.log"
        path.write_text("\n".join(runner.strip_ansi(line) for line in self._lines) + "\n")
        self.notify(f"saved to {path.name}")
