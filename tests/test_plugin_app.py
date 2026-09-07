"""What a plugin can actually do to the running app.

These drive a real Textual app in headless mode, because the whole point of
the plugin system is the widget tree: a tab that is not mounted, a key that is
not bound and an action that is not installed are all silent failures the
unit tests above cannot see.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import DataTable, Input, Static, TabPane

from pb.app import PbApp
from pb.plugins.api import RunRequest
from pb.plugins.store import Store

VETO = """\
from pb.plugins import Plugin


class Stopper(Plugin):
    def before_run(self, request):
        request.veto("not on a Friday")
"""

WRAPS_AN_ACTION = """\
from pb.plugins import Plugin

CALLS = []


class Wrapper(Plugin):
    def actions(self):
        return {"reload": self.reload_first}

    def reload_first(self):
        CALLS.append("mine")
        base = self.base_action("reload")
        base()
        CALLS.append("base")
"""

ODD_FOCUS = """\
from pb.plugins import Plugin, TabSpec
from textual.widgets import Static


class Odd(Plugin):
    def tabs(self):
        yield TabSpec(
            id="tab-odd",
            title="Odd",
            factory=lambda: Static("nothing here takes focus", id="odd-body"),
            focus="#not-even-there",
        )
"""

EXPLODES = """\
from pb.plugins import CheckResult, KeySpec, Plugin, TabSpec
from textual.widgets import Static


class Exploder(Plugin):
    def tabs(self):
        yield TabSpec(id="tab-boom", title="Boom", factory=lambda: Static("boom"))

    def status_bar(self):
        raise RuntimeError("boom")

    def doctor(self):
        yield CheckResult("never reached", True, "")
"""


def drive(app: PbApp, scenario: Callable[[Any], Coroutine[Any, Any, None]]) -> None:
    """Run one headless scenario against `app`.

    pb's tests are synchronous and the project has no async plugin for pytest,
    so the event loop is started here rather than per test.
    """

    async def go() -> None:
        async with app.run_test() as pilot:
            await settled(app, pilot)
            await scenario(pilot)

    asyncio.run(go())


async def settled(app: PbApp, pilot) -> None:
    """Wait for the first reload — it runs in a thread — then a repaint."""
    for _ in range(100):
        await pilot.pause()
        if app.playbooks:
            return
    raise AssertionError("the repo never finished loading")


@pytest.fixture
def probe(linked_plugin) -> Callable[[], Any]:
    """The probe plugin from conftest, plus the module it recorded events in."""

    def build():
        linked_plugin(name="pb-probe", module="pb_probe")
        return None

    return build


def events() -> list[str]:
    import pb_probe

    return pb_probe.EVENTS


# --- what a plugin adds ---------------------------------------------------


def test_a_plugin_tab_is_mounted_and_focusable(repo_root: Path, probe) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        assert app.plugins.failures == []
        assert [p.name for p in app.plugins.active] == ["pb-probe"]
        assert "tab-probe" in [pane.id for pane in app.query(TabPane)]
        # Registered for focus, so activating the tab moves focus into it.
        assert app.tab_tables["tab-probe"] == "#probe-table"
        app.action_tab("tab-probe")
        await pilot.pause()
        assert app.query_one("#probe-table").has_focus
        # activate() added the columns, reloaded() filled the rows in.
        assert app.query_one("#probe-table", DataTable).row_count == len(app.playbooks)

    drive(app, scenario)


def test_a_tab_whose_focus_target_cannot_take_focus_still_opens(
    repo_root: Path, linked_plugin
) -> None:
    """`focus` is a selector, so a plugin can name something unfocusable, or
    something that is not there at all. Neither is worth a crash."""
    linked_plugin(name="pb-odd", module="pb_odd", body=ODD_FOCUS)
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        app.action_tab("tab-odd")
        await pilot.pause()
        assert app.query_one("#tab-odd", TabPane).id == "tab-odd"
        assert app.plugins.is_active("pb-odd")

    drive(app, scenario)


def test_a_plugin_key_on_a_core_table_fires_its_action(repo_root: Path, probe) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        events().clear()
        app.query_one("#playbooks", DataTable).focus()
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert "shout" in events()

    drive(app, scenario)


def test_a_plugin_key_bound_to_the_app_works_from_any_tab(repo_root: Path, probe) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        events().clear()
        app.action_tab("tab-inventory")
        await pilot.pause()
        await pilot.press("ctrl+j")
        await pilot.pause()
        assert "shout" in events()

    drive(app, scenario)


def test_activate_and_reloaded_both_fire_and_in_that_order(repo_root: Path, probe) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        assert events().index("activate") < events().index("reloaded")
        before = events().count("reloaded")
        app.reload()
        for _ in range(100):
            await pilot.pause()
            if events().count("reloaded") > before:
                return
        raise AssertionError("reloaded() did not fire again")

    drive(app, scenario)


def test_a_plugin_adds_rows_to_doctor(repo_root: Path, probe) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        assert [(c.name, c.ok) for c in app.plugins.doctor()] == [("probe check", True)]

    drive(app, scenario)


def test_a_plugin_appends_to_a_detail_pane_and_the_status_bar(
    repo_root: Path, probe
) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        detail = str(app.query_one("#playbook-detail", Static).render())
        assert "probe was here" in detail
        assert "probe" in str(app.query_one("#statusbar", Static).render())

    drive(app, scenario)


def test_a_plugin_puts_its_commands_in_the_palette(repo_root: Path, probe) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        assert [command.title for _, command in app.plugins.commands()] == ["Shout"]

    drive(app, scenario)


# --- replacing what the base app does -------------------------------------


def test_a_plugin_can_replace_an_action_the_app_already_has(
    repo_root: Path, probe
) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        events().clear()
        await pilot.press("question_mark")
        await pilot.pause()
        assert "help" in events()
        # The built-in is still reachable, so a plugin can wrap it.
        assert "base-help" in events()
        # …and the built-in help screen did not open.
        assert app.screen_stack[-1] is app.screen_stack[0]

    drive(app, scenario)


def test_a_replacement_can_call_the_action_it_replaced(
    repo_root: Path, linked_plugin
) -> None:
    linked_plugin(name="pb-wrap", module="pb_wrap", body=WRAPS_AN_ACTION)
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        import pb_wrap

        pb_wrap.CALLS.clear()
        await pilot.press("ctrl+r")
        await settled(app, pilot)
        assert pb_wrap.CALLS == ["mine", "base"]

    drive(app, scenario)


# --- runs ------------------------------------------------------------------


def test_before_run_can_edit_the_command_and_the_environment(
    repo_root: Path, probe
) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        events().clear()
        request = app._authorize(["ansible-playbook", "web.yml"], "web", "run")
        assert request is not None
        assert request.argv[-1] == "--probed"
        assert request.env == {"PROBE": "1"}
        assert "before:run" in events()

    drive(app, scenario)


def test_a_veto_stops_the_run_and_says_who_stopped_it(
    repo_root: Path, linked_plugin
) -> None:
    linked_plugin(name="pb-stopper", module="pb_stopper", body=VETO)
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        assert app._authorize(["ansible-playbook", "web.yml"], "web", "run") is None
        await pilot.pause()   # notify() posts a message; let it land
        messages = [str(n.message) for n in app._notifications]
        assert any("pb-stopper" in m and "not on a Friday" in m for m in messages)

    drive(app, scenario)


def test_what_a_plugin_rewrote_is_what_the_user_is_shown(
    repo_root: Path, probe
) -> None:
    """The confirmation has to describe the command that will run."""
    probe()
    app = PbApp(repo_root)
    shown: list[list[str]] = []

    async def scenario(pilot) -> None:
        app._confirm_apply = lambda pb, argv, go: shown.append(argv)
        app.query_one("#playbooks", DataTable).focus()
        app._playbook_action("run")
        await pilot.pause()
        assert shown and shown[0][-1] == "--probed"

    drive(app, scenario)


def test_after_run_sees_the_exit_code_and_the_recorded_run(
    repo_root: Path, probe
) -> None:
    """Driven through RunScreen, so the hook fires where it really fires."""
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        events().clear()
        app.launch(["/bin/sh", "-c", "exit 3"], "a short run")
        for _ in range(200):
            await pilot.pause()
            if any(e.startswith("after:") for e in events()):
                break
        assert "after:3" in events()

    drive(app, scenario)


# --- containment -----------------------------------------------------------


def test_a_hook_that_raises_switches_that_plugin_off(
    repo_root: Path, linked_plugin
) -> None:
    linked_plugin(name="pb-boom", module="pb_boom", body=EXPLODES)
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        assert app.plugins.active == []
        (failure,) = [f for f in app.plugins.failures if f.name == "pb-boom"]
        assert failure.stage == "runtime"
        assert "status_bar()" in failure.message
        # Its tab goes with it: an empty tab explains nothing.
        assert "tab-boom" not in [pane.id for pane in app.query(TabPane)]
        # And it is not asked for Doctor rows any more.
        assert [c.name for c in app.plugins.doctor()] == ["plugin pb-boom"]

    drive(app, scenario)


def test_a_broken_plugin_leaves_the_rest_of_the_app_working(
    repo_root: Path, linked_plugin
) -> None:
    linked_plugin(name="pb-boom", module="pb_boom", body=EXPLODES)
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        assert app.playbooks
        assert app.query_one("#playbooks", DataTable).row_count == len(app.playbooks)
        assert "the repo" not in str(app.query_one("#statusbar", Static).render())

    drive(app, scenario)


def test_a_plugin_that_failed_to_load_is_a_failed_doctor_check(
    repo_root: Path, linked_plugin
) -> None:
    linked_plugin(name="pb-bad", module="pb_bad", body="raise RuntimeError('boom')")
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        rows = app.plugins.doctor()
        assert [(r.name, r.ok) for r in rows] == [("plugin pb-bad", False)]
        assert "boom" in rows[0].detail

    drive(app, scenario)


# --- the off switch and the Plugins tab -------------------------------------


def test_no_plugins_loads_none_of_them(repo_root: Path, probe) -> None:
    probe()
    app = PbApp(repo_root, plugins=False)

    async def scenario(pilot) -> None:
        assert app.plugins.active == []
        assert "tab-probe" not in [pane.id for pane in app.query(TabPane)]
        # Still listed, so the Plugins tab can say why it is not loaded.
        assert [r.name for r in app.plugin_records] == ["pb-probe"]
        assert "--no-plugins" in str(app._plugin_state(app.plugin_records[0]))

    drive(app, scenario)


def test_the_plugins_tab_lists_what_is_installed(repo_root: Path, probe) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        await pilot.press("8")
        await pilot.pause()
        assert app.query_one("#plugins", DataTable).row_count == 1
        assert app.plugin_record.name == "pb-probe"
        assert "loaded" in str(app._plugin_state(app.plugin_record))
        detail = str(app.query_one("#plugin-detail", Static).render())
        assert "pb-probe" in detail
        assert "before_run" in detail

    drive(app, scenario)


def test_the_plugins_tab_explains_itself_when_nothing_is_installed(
    repo_root: Path,
) -> None:
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        await pilot.press("8")
        await pilot.pause()
        assert app.query_one("#plugins", DataTable).row_count == 0
        assert "No plugins installed" in str(
            app.query_one("#plugin-detail", Static).render()
        )

    drive(app, scenario)


def test_enabling_and_disabling_from_the_tab_is_written_down(
    repo_root: Path, probe, store: Store
) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        await pilot.press("8")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert store.get("pb-probe").enabled is False
        # It keeps working until pb restarts — nothing is torn out from under
        # a live UI — and the tab says so.
        assert app.plugins.is_active("pb-probe")

    drive(app, scenario)


def test_a_plugin_reads_the_repo_through_the_api(repo_root: Path, probe) -> None:
    probe()
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        (plugin,) = app.plugins.active
        assert plugin.repo.root == repo_root
        assert [p.name for p in plugin.playbooks] == [p.name for p in app.playbooks]
        assert plugin.inventory is app.inventory
        assert plugin.data_dir == Store().data_dir_for("pb-probe")

    drive(app, scenario)


def test_a_run_request_a_plugin_never_touches_is_unchanged(repo_root: Path) -> None:
    """With no plugins loaded, the command is exactly what pb built."""
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        request = app._authorize(["ansible-playbook", "web.yml"], "web", "run")
        assert isinstance(request, RunRequest)
        assert request.argv == ["ansible-playbook", "web.yml"]
        assert request.env == {}

    drive(app, scenario)


ASYNC_ACTION = """\
from pb.plugins import Plugin

SEEN = []


class Async(Plugin):
    def actions(self):
        return {"ok_async": self.fine, "bad_async": self.boom, "with_param": self.param}

    async def fine(self):
        SEEN.append("fine")

    async def boom(self):
        raise RuntimeError("boom")

    def param(self, value):
        SEEN.append(value)
"""


def test_an_async_action_is_awaited_and_its_failure_contained(
    repo_root: Path, linked_plugin
) -> None:
    """Textual awaits what an action returns, which is outside the guard the
    call itself ran under — so the await has to be guarded too."""
    linked_plugin(name="pb-async", module="pb_async", body=ASYNC_ACTION)
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        import pb_async

        pb_async.SEEN.clear()
        await app.run_action("ok_async")
        assert pb_async.SEEN == ["fine"]

        await app.run_action("bad_async")
        await pilot.pause()
        assert app.plugins.active == []
        (failure,) = [f for f in app.plugins.failures if f.name == "pb-async"]
        assert "bad_async" in failure.message

    drive(app, scenario)


def test_an_action_keeps_its_parameters(repo_root: Path, linked_plugin) -> None:
    linked_plugin(name="pb-async", module="pb_async", body=ASYNC_ACTION)
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        import pb_async

        pb_async.SEEN.clear()
        await app.run_action("with_param('hello')")
        assert pb_async.SEEN == ["hello"]

    drive(app, scenario)


def test_a_replacement_stops_shadowing_once_its_plugin_is_switched_off(
    repo_root: Path, linked_plugin
) -> None:
    """A dead plugin must not leave a key doing nothing at all."""
    linked_plugin(name="pb-wrap", module="pb_wrap", body=WRAPS_AN_ACTION)
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        import pb_wrap

        (wrapper,) = app.plugins.active
        app.plugins._disable(wrapper, "on purpose", RuntimeError("test"))
        pb_wrap.CALLS.clear()

        await pilot.press("ctrl+r")
        await settled(app, pilot)
        # Its replacement stood aside, and pb reloaded the way it always does.
        assert pb_wrap.CALLS == []
        assert app.playbooks

    drive(app, scenario)


def test_installing_from_the_plugins_tab_asks_first_then_clones(
    repo_root: Path, plugin_git_repo, store: Store
) -> None:
    """The interactive path: the prompt, the trust notice, then a git clone in
    a worker thread."""
    upstream = plugin_git_repo(name="pb-probe")
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        await pilot.press("8", "i")
        for _ in range(10):
            await pilot.pause()
        app.screen.query_one("#entry", Input).value = str(upstream)
        await pilot.press("enter")
        for _ in range(10):
            await pilot.pause()

        # What is about to be cloned, and what that means, before anything runs.
        body = " ".join(str(widget.render()) for widget in app.screen.query(Static))
        assert str(upstream) in body
        assert "with your permissions" in body
        assert store.records() == []

        await pilot.press("enter")   # Confirm focuses its accept button
        for _ in range(400):
            await pilot.pause()
            if store.get("pb-probe"):
                break
        record = store.get("pb-probe")
        assert record is not None
        assert len(record.commit) == 40
        await pilot.pause()

        assert app.query_one("#plugins", DataTable).row_count == 1
        # Cloned, recorded, and not loaded: importing it needs a restart.
        assert "pending restart" in str(app._plugin_state(record))
        assert not app.plugins.is_active("pb-probe")

    drive(app, scenario)


def test_declining_the_install_clones_nothing(
    repo_root: Path, plugin_git_repo, store: Store
) -> None:
    upstream = plugin_git_repo(name="pb-probe")
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        await pilot.press("8", "i")
        for _ in range(10):
            await pilot.pause()
        app.screen.query_one("#entry", Input).value = str(upstream)
        await pilot.press("enter")
        for _ in range(10):
            await pilot.pause()
        await pilot.press("escape")
        for _ in range(20):
            await pilot.pause()
        assert store.records() == []
        assert list(store.plugins_dir.glob("*")) == [] or not store.plugins_dir.exists()

    drive(app, scenario)


def test_a_source_the_tab_cannot_make_sense_of_is_a_message(
    repo_root: Path, store: Store
) -> None:
    app = PbApp(repo_root)

    async def scenario(pilot) -> None:
        await pilot.press("8", "i")
        for _ in range(10):
            await pilot.pause()
        app.screen.query_one("#entry", Input).value = "not a source!"
        await pilot.press("enter")
        for _ in range(10):
            await pilot.pause()
        assert any(
            "is not a plugin source" in str(n.message) for n in app._notifications
        )
        assert store.records() == []

    drive(app, scenario)
