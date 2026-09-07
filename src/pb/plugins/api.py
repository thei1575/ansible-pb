"""The surface a plugin is written against.

Everything in here is what a third-party plugin imports, so it is the part of
pb that cannot change without a new `api` number in the manifest. Plugins get
dataclasses for the things they contribute and a `Plugin` base class whose
methods are all optional: override the hooks you need and ignore the rest.

A plugin is ordinary Python running in pb's own process. It can read the repo,
add tabs and keys, and replace an existing action outright — see
`docs/PLUGINS.md`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text

if TYPE_CHECKING:  # pragma: no cover - imports for type checkers only
    from textual.widget import Widget

    from .. import history, hoststatus, meta
    from ..app import PbApp

# Bumped when a change to anything in this module would break a plugin written
# against the previous number. A manifest declares which one it was written
# for and the loader refuses anything else.
API_VERSION = 1

# The detail pane on each core tab, named for the `detail()` hook. A plugin
# sees the same subject the pane is rendering.
PANES = ("playbook", "host", "role", "vault", "status", "history")


@dataclass
class TabSpec:
    """A whole tab of your own.

    `factory` is called once, on mount, and must return the widget that fills
    the pane — usually a container. `focus` is a selector for the widget that
    should take focus when the tab is activated, and it has to name something
    focusable (a `DataTable`, an `Input`, a container with `can_focus`): a
    `Static` will not take focus, and key bindings on your widgets do not fire
    until something inside the pane has it. Without `focus`, pb leaves focus
    where it was.
    """

    id: str
    title: str
    factory: Callable[[], Widget]
    focus: str | None = None
    # Place the tab relative to an existing one, by pane id. Default: last.
    before: str | None = None
    after: str | None = None


@dataclass
class KeySpec:
    """One key binding, attached to a widget that already exists.

    `target` is a widget id — `playbooks`, `hosts`, `roles`, `vaults`,
    `status`, `history`, `doctor`, one of your own, or the literal `app` for a
    binding that works everywhere. `action` is a Textual action string, so an
    action on the app needs the `app.` namespace: `app.my_action`.
    """

    target: str
    key: str
    action: str
    description: str = ""
    show: bool = True
    priority: bool = False


@dataclass
class Command:
    """An entry in the command palette (`ctrl+p`)."""

    title: str
    callback: Callable[[], Any]
    help: str = ""


@dataclass
class CheckResult:
    """One row on the Doctor tab.

    `ok` is True for a pass, False for a failure and None for a warning, the
    same three states the built-in checks use.
    """

    name: str
    ok: bool | None
    detail: str = ""


@dataclass
class RunRequest:
    """A command pb is about to run, before it runs.

    `before_run` hooks receive this and may edit it: change `argv`, add
    environment variables for the child process, or call `veto()` to stop the
    run. Whatever `argv` ends up as is what the user is shown and what
    executes — pb never runs something it has not displayed.
    """

    argv: list[str]
    label: str
    # "run", "check", "syntax" for a playbook; "ad-hoc" for ping/facts and
    # anything a plugin launches itself; "repeat" for a re-run from History.
    mode: str = "ad-hoc"
    playbook: meta.Playbook | None = None
    env: dict[str, str] = field(default_factory=dict)
    vetoed: bool = False
    reason: str = ""
    # The plugin that vetoed, filled in by pb so the message can name it.
    vetoed_by: str = ""

    def veto(self, reason: str = "") -> None:
        """Stop this run. `reason` is shown to the user."""
        self.vetoed = True
        self.reason = reason or self.reason


@dataclass
class RunResult:
    """A finished run, handed to `after_run` once it has been recorded."""

    argv: list[str]
    label: str
    exit_code: int
    duration: float
    recap: dict[str, dict[str, int]] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    run: history.Run | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class Plugin:
    """Subclass this, and override the hooks you want.

    The loader fills in `name`, `version`, `root` and `data_dir` from the
    manifest before `activate()` is called, and `app` is set by then too, so
    `activate()` can query the UI. Every hook is optional and every hook is
    allowed to fail: pb catches the exception, reports it on the Plugins tab
    and disables the plugin for the rest of the session rather than dying.

    Threads: `doctor()` runs in a worker thread, so it may shell out. Every
    other hook runs on the UI thread and must not block — use
    `self.app.run_worker` or pb's own `_launch` for anything slow.
    """

    # Filled in by the loader from pb-plugin.toml.
    name: str = ""
    version: str = ""
    summary: str = ""
    root: Path = Path()
    data_dir: Path = Path()
    app: PbApp = None  # type: ignore[assignment]

    # --- lifecycle ---------------------------------------------------

    def activate(self) -> None:
        """Called once, after the UI is mounted and your tabs and keys exist."""

    def deactivate(self) -> None:
        """Called when pb is shutting down cleanly."""

    # --- what the plugin contributes ---------------------------------

    def tabs(self) -> Iterable[TabSpec]:
        return ()

    def keys(self) -> Iterable[KeySpec]:
        return ()

    def actions(self) -> Mapping[str, Callable[..., Any]]:
        """Actions to install on the app, by name without the `action_` prefix.

        A name pb already uses replaces the built-in — `{"run": self.my_run}`
        takes over `r` on the Playbooks tab. Call `self.base_action("run")` to
        get what was there before, so a plugin can wrap rather than replace.
        """
        return {}

    def commands(self) -> Iterable[Command]:
        return ()

    # --- reacting to the app -----------------------------------------

    def doctor(self) -> Iterable[CheckResult]:
        """Extra Doctor rows. Runs in a worker thread; may shell out."""
        return ()

    def reloaded(self) -> None:
        """Called every time pb has re-read the repo and repainted the tabs.

        `activate()` runs before the first load, so this — not `activate()` —
        is where a tab of your own fills itself in: it fires on start-up, on
        ctrl+r, and after every run.
        """

    def before_run(self, request: RunRequest) -> None:
        """Inspect, edit or veto a command before it runs."""

    def after_run(self, result: RunResult) -> None:
        """Called once a run has finished and been written to history.

        Only for runs pb streamed on the run screen — the same ones that end
        up in `.pb/runs`. Anything that leaves the TUI for a real terminal (an
        ssh session, `ansible-vault edit`, a playbook with `vars_prompt`) is
        not recorded and does not arrive here; `before_run` still sees it.
        """

    def detail(self, pane: str, subject: Any) -> Text | str | None:
        """Extra text appended to a core detail pane.

        `pane` is one of `PANES`; `subject` is the `Playbook`, `Host`, `Role`,
        `Vault` or `Run` the pane is showing. Return None for panes you do not
        care about.
        """
        return None

    def status_bar(self) -> Text | str | None:
        """A segment appended to the top status strip on every reload."""
        return None

    # --- what a plugin gets to use -----------------------------------

    @property
    def repo(self) -> meta.Repo:
        return self.app.repo

    @property
    def inventory(self) -> meta.Inventory:
        return self.app.inventory

    @property
    def playbooks(self) -> list[meta.Playbook]:
        return self.app.playbooks

    @property
    def roles(self) -> list[meta.Role]:
        return self.app.roles

    @property
    def vaults(self) -> list[meta.Vault]:
        return self.app.vaults

    @property
    def runs(self) -> list[history.Run]:
        return self.app.runs

    @property
    def host_status(self) -> dict[str, hoststatus.HostStatus]:
        return self.app.host_status

    def base_action(self, name: str) -> Callable[..., Any] | None:
        """The action `name` had before this plugin replaced it, if any."""
        return self.app.plugins.base_action(self.name, name)

    def launch(self, argv: list[str], label: str, mode: str = "ad-hoc") -> None:
        """Run a command the way pb runs its own: full-screen, streamed, recorded."""
        self.app.launch(argv, label, mode=mode)

    def notify(self, message: str, severity: str = "information", timeout: float = 5) -> None:
        self.app.notify(message, severity=severity, timeout=timeout)  # type: ignore[arg-type]

    def view(self, title: str, body: str, lexer: str | None = None) -> None:
        """Show text in pb's scrollable viewer."""
        from ..widgets import Viewer

        self.app.push_screen(Viewer(title, body, lexer))

    def reload(self) -> None:
        """Re-read the repo and repaint every tab."""
        self.app.reload()
