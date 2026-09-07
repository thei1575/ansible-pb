"""Binding loaded plugins to the running app.

This is the only module that knows both sides: it takes what a plugin
contributes and puts it into pb's widget tree, and it calls the hooks with
every exception caught. The rule is that a broken plugin costs the user that
plugin and nothing else — a hook that raises is reported, and the plugin is
switched off for the rest of the session so it cannot raise on every keystroke.
"""

from __future__ import annotations

import traceback
from collections.abc import Awaitable, Callable, Iterable
from contextlib import contextmanager, suppress
from inspect import isawaitable
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.widgets import TabbedContent, TabPane

from .api import CheckResult, Command, KeySpec, Plugin, RunRequest, RunResult, TabSpec
from .loader import Failure, Loaded

if TYPE_CHECKING:  # pragma: no cover
    from ..app import PbApp

# A binding target of this name means "everywhere", i.e. the app itself.
APP_TARGET = "app"


class PluginHost:
    """Everything the app does with its plugins goes through here."""

    def __init__(self, app: PbApp, loaded: Loaded) -> None:
        self.app = app
        self.loaded = loaded
        # Plugins still trusted to run. A hook that raises removes its plugin
        # from here; `loaded.plugins` keeps the full list for the Plugins tab.
        self.active: list[Plugin] = list(loaded.plugins)
        for plugin in self.active:
            plugin.app = app
        # Pane ids each plugin added, so a plugin that dies takes its own tabs
        # with it rather than leaving an empty one behind.
        self.panes: dict[str, list[str]] = {}
        # Whatever `action_<name>` was before a plugin replaced it, per plugin,
        # so `Plugin.base_action` can wrap instead of replace.
        self._base_actions: dict[tuple[str, str], Callable[..., Any] | None] = {}
        # Plugin pane id -> selector to focus when the tab is activated.
        self.tab_focus: dict[str, str] = {}
        self.failures: list[Failure] = list(loaded.failures)

    # --- introspection --------------------------------------------------

    @property
    def any(self) -> bool:
        return bool(self.loaded.plugins or self.failures or self.loaded.records)

    def is_active(self, name: str) -> bool:
        return any(p.name == name for p in self.active)

    def failure_for(self, name: str) -> Failure | None:
        return next((f for f in self.failures if f.name == name), None)

    def plugin(self, name: str) -> Plugin | None:
        return self.loaded.by_name(name)

    def base_action(self, plugin: str, action: str) -> Callable[..., Any] | None:
        return self._base_actions.get((plugin, action))

    # --- error containment ----------------------------------------------

    @contextmanager
    def _guard(self, plugin: Plugin, doing: str):
        """Run plugin code; on failure disable the plugin and say so once."""
        try:
            yield
        except Exception as exc:  # third-party code
            self._disable(plugin, doing, exc)

    def _disable(self, plugin: Plugin, doing: str, exc: Exception) -> None:
        if plugin in self.active:
            self.active.remove(plugin)
        self._remove_panes(plugin)
        message = f"{type(exc).__name__}: {exc}"
        self.failures.append(
            Failure(
                plugin.name,
                f"{doing} raised {message}",
                detail=traceback.format_exc(),
                stage="runtime",
            )
        )
        # Before the app is mounted there is nothing to notify. The failure is
        # recorded either way, and Doctor will show it.
        with suppress(Exception):
            self.app.notify(
                f"plugin {plugin.name} failed in {doing} and was switched off "
                f"for this session — {message}",
                severity="error",
                timeout=12,
            )

    def _remove_panes(self, plugin: Plugin) -> None:
        """Take a dead plugin's tabs away — an empty tab explains nothing."""
        for pane_id in self.panes.pop(plugin.name, []):
            self.tab_focus.pop(pane_id, None)
            self.app.tab_tables.pop(pane_id, None)
            with suppress(Exception):
                self.app.query_one(TabbedContent).remove_pane(pane_id)

    # --- installation ---------------------------------------------------

    async def install(self) -> None:
        """Add every plugin's tabs, keys and actions, then activate them.

        Tabs first, and awaited: a plugin's `keys()` binds to widgets its own
        tab owns and `activate()` queries them, so the panes have to be
        mounted — `add_pane` only promises to mount them.
        """
        for plugin in list(self.active):
            with self._guard(plugin, "tabs()"):
                await self._add_tabs(plugin, plugin.tabs())
        for plugin in list(self.active):
            with self._guard(plugin, "actions()"):
                self._add_actions(plugin, plugin.actions())
        for plugin in list(self.active):
            with self._guard(plugin, "keys()"):
                self._add_keys(plugin, plugin.keys())
        for plugin in list(self.active):
            with self._guard(plugin, "activate()"):
                plugin.activate()
        # The footer is built from the bindings, and they have just changed.
        self.app.refresh_bindings()

    async def _add_tabs(self, plugin: Plugin, specs: Iterable[TabSpec]) -> None:
        tabs = self.app.query_one(TabbedContent)
        for spec in specs:
            pane = TabPane(spec.title, spec.factory(), id=spec.id)
            await tabs.add_pane(pane, before=spec.before, after=spec.after)
            self.panes.setdefault(plugin.name, []).append(spec.id)
            if spec.focus:
                self.tab_focus[spec.id] = spec.focus
                self.app.tab_tables[spec.id] = spec.focus

    def _add_actions(self, plugin: Plugin, actions: Any) -> None:
        for name, callback in dict(actions).items():
            attr = f"action_{name}"
            # getattr finds the class method for a built-in action, or an
            # earlier plugin's replacement. Either way it is what this plugin
            # is taking over from.
            self._base_actions[(plugin.name, name)] = getattr(self.app, attr, None)
            setattr(self.app, attr, self._wrap_action(plugin, name, callback))

    def _wrap_action(self, plugin: Plugin, name: str, callback: Callable[..., Any]):
        def invoke(*args: Any, **kwargs: Any) -> Any:
            # A plugin switched off mid-session leaves its replacement in
            # place, so hand the key back to whatever it took over from
            # rather than letting the key go dead.
            if not self.is_active(plugin.name):
                base = self.base_action(plugin.name, name)
                return base(*args, **kwargs) if base else None
            with self._guard(plugin, f"action {name}"):
                result = callback(*args, **kwargs)
                # Textual awaits an awaitable an action returns, which would
                # be outside the guard above. Await it inside one instead.
                if isawaitable(result):
                    return self._guarded_await(plugin, name, result)
                return result
            return None

        invoke.__name__ = f"action_{name}"
        invoke.__doc__ = getattr(callback, "__doc__", None) or f"{plugin.name}: {name}"
        return invoke

    async def _guarded_await(self, plugin: Plugin, name: str, awaitable: Awaitable[Any]):
        with self._guard(plugin, f"action {name}"):
            return await awaitable
        return None

    def _add_keys(self, plugin: Plugin, specs: Iterable[KeySpec]) -> None:
        for spec in specs:
            target = (
                self.app
                if spec.target == APP_TARGET
                else self.app.query_one(f"#{spec.target}")
            )
            target._bindings.bind(
                spec.key,
                spec.action,
                spec.description or f"{plugin.name}",
                show=spec.show,
                priority=spec.priority,
            )

    # --- hooks -----------------------------------------------------------

    def reloaded(self) -> None:
        for plugin in list(self.active):
            with self._guard(plugin, "reloaded()"):
                plugin.reloaded()

    def before_run(self, request: RunRequest) -> bool:
        """Let plugins edit or stop a command. False means it must not run."""
        for plugin in list(self.active):
            with self._guard(plugin, "before_run()"):
                plugin.before_run(request)
                if request.vetoed:
                    request.vetoed_by = plugin.name
                    return False
        return True

    def after_run(self, result: RunResult) -> None:
        for plugin in list(self.active):
            with self._guard(plugin, "after_run()"):
                plugin.after_run(result)

    def doctor(self) -> list[CheckResult]:
        """Plugin checks, plus a row for every plugin that failed to load.

        Called from the Doctor worker thread, so a check may shell out.
        """
        rows: list[CheckResult] = []
        for failure in self.failures:
            rows.append(
                CheckResult(f"plugin {failure.name}", False, f"{failure.stage}: {failure.message}")
            )
        for plugin in list(self.active):
            with self._guard(plugin, "doctor()"):
                for check in plugin.doctor():
                    rows.append(check)
        return rows

    def detail(self, pane: str, subject: object) -> list[Text]:
        """Extra text for a core detail pane, one block per plugin."""
        blocks: list[Text] = []
        for plugin in list(self.active):
            with self._guard(plugin, "detail()"):
                extra = plugin.detail(pane, subject)
                if extra:
                    blocks.append(extra if isinstance(extra, Text) else Text(str(extra)))
        return blocks

    def status_bar(self) -> list[Text]:
        segments: list[Text] = []
        for plugin in list(self.active):
            with self._guard(plugin, "status_bar()"):
                extra = plugin.status_bar()
                if extra:
                    segments.append(extra if isinstance(extra, Text) else Text(str(extra)))
        return segments

    def commands(self) -> list[tuple[Plugin, Command]]:
        found: list[tuple[Plugin, Command]] = []
        for plugin in list(self.active):
            with self._guard(plugin, "commands()"):
                found.extend((plugin, command) for command in plugin.commands())
        return found

    def shutdown(self) -> None:
        for plugin in list(self.active):
            with self._guard(plugin, "deactivate()"):
                plugin.deactivate()


class PluginCommands(Provider):
    """Puts every plugin's commands into the command palette (ctrl+p)."""

    def _commands(self) -> list[tuple[str, str, Callable[[], Any]]]:
        host = getattr(self.app, "plugins", None)
        if host is None:
            return []
        return [
            (f"{plugin.name}: {command.title}", command.help, command.callback)
            for plugin, command in host.commands()
        ]

    async def discover(self) -> Hits:
        for title, help_text, callback in self._commands():
            yield DiscoveryHit(title, callback, help=help_text or None)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for title, help_text, callback in self._commands():
            score = matcher.match(title)
            if score > 0:
                yield Hit(score, matcher.highlight(title), callback, help=help_text or None)
