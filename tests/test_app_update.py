"""The update prompt, driven through the real app.

Textual's `run_test` is async and pb has no async test plumbing, so each
scenario is a coroutine handed to `asyncio.run`. Nothing here reaches the
network: `update.check` is replaced with an answer.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Button

from pb import app, meta, update
from pb.widgets import UpdatePrompt, Viewer

NOTES = "## [0.2.0]\n\n### Added\n\n* Something worth having.\n"
RELEASE = update.Release(
    version="0.2.0", tag="v0.2.0", notes=NOTES, url="https://example.invalid/v0.2.0"
)


def drive(scenario: Callable[[], Coroutine[Any, Any, None]]) -> None:
    asyncio.run(scenario())


async def settle(pilot: Any, ready: Callable[[], bool], tries: int = 200) -> bool:
    """Let the app run until `ready`, rather than guessing at a sleep."""
    for _ in range(tries):
        if ready():
            return True
        await pilot.pause(0.02)
    return ready()


async def press(pilot: Any, screen: Any, button: str) -> None:
    """Click a button once it is on screen.

    The prompt is pushed by a worker while the app is still starting, so its
    widgets arrive over a frame or two rather than all at once.
    """
    assert await settle(pilot, lambda: bool(screen.query(button))), f"no {button} button"
    await pilot.click(button)


@pytest.fixture
def offered(monkeypatch: pytest.MonkeyPatch) -> None:
    """A check that finds 0.2.0, installed the way `uv tool install` puts it."""
    monkeypatch.setattr(update, "check", lambda current, **kw: update.Result(RELEASE, True))
    monkeypatch.setattr(update, "install_method", lambda *a, **k: "uv")


def test_a_new_version_is_offered_when_the_app_opens(repo_root: Path, offered: None) -> None:
    async def scenario() -> None:
        instance = app.PbApp(repo_root)
        async with instance.run_test() as pilot:
            assert await settle(pilot, lambda: isinstance(instance.screen, UpdatePrompt))
            prompt = instance.screen
            assert isinstance(prompt, UpdatePrompt)
            # The version you have and the one on offer, then the changelog.
            assert "0.2.0" in prompt._title
            assert app.__version__ in prompt._title
            assert "Something worth having." in prompt._notes
            # pb never runs a command it has not shown you.
            assert prompt._command == (
                f"uv tool install --force {update.GIT_URL}@v0.2.0"
            )

    drive(scenario)


def test_skipping_remembers_the_version_and_closes(repo_root: Path, offered: None) -> None:
    async def scenario() -> None:
        instance = app.PbApp(repo_root)
        async with instance.run_test() as pilot:
            assert await settle(pilot, lambda: isinstance(instance.screen, UpdatePrompt))
            await press(pilot, instance.screen, "#skip")
            await pilot.pause()
            assert not isinstance(instance.screen, UpdatePrompt)
        assert update.load_state()["skipped"] == "0.2.0"

    drive(scenario)


def test_escape_closes_without_remembering_anything(repo_root: Path, offered: None) -> None:
    async def scenario() -> None:
        instance = app.PbApp(repo_root)
        async with instance.run_test() as pilot:
            assert await settle(pilot, lambda: isinstance(instance.screen, UpdatePrompt))
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(instance.screen, UpdatePrompt)
        assert "skipped" not in update.load_state()

    drive(scenario)


def test_accepting_runs_exactly_the_command_it_showed(
    repo_root: Path, offered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `meta.capture` is how pb runs everything, the repo's own git calls
    # included, so keep only what the installer was asked to do.
    ran: list[list[str]] = []

    def fake_capture(argv: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
        if argv[0] == "uv":
            ran.append(argv)
            return 0, "Installed 1 executable: pb"
        return 127, "not found"

    monkeypatch.setattr(meta, "capture", fake_capture)

    async def scenario() -> None:
        instance = app.PbApp(repo_root)
        async with instance.run_test() as pilot:
            assert await settle(pilot, lambda: isinstance(instance.screen, UpdatePrompt))
            shown = instance.screen._command
            await press(pilot, instance.screen, "#update")
            assert await settle(pilot, lambda: bool(ran)), "the update never ran"
            assert [" ".join(argv) for argv in ran] == [shown]
        # A version you installed is not a version you skipped.
        assert "skipped" not in update.load_state()

    drive(scenario)


def test_a_failed_install_shows_the_output_instead_of_claiming_success(
    repo_root: Path, offered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        meta,
        "capture",
        lambda argv, cwd, timeout=120: (1, "error: no such ref v0.2.0"),
    )

    async def scenario() -> None:
        instance = app.PbApp(repo_root)
        async with instance.run_test() as pilot:
            assert await settle(pilot, lambda: isinstance(instance.screen, UpdatePrompt))
            await press(pilot, instance.screen, "#update")
            assert await settle(pilot, lambda: isinstance(instance.screen, Viewer))
            viewer = instance.screen
            assert isinstance(viewer, Viewer)
            assert "failed" in viewer._title
            assert "no such ref" in viewer._body

    drive(scenario)


def test_no_update_check_never_asks(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object, **kwargs: object) -> update.Result:
        raise AssertionError("checked for updates anyway")

    monkeypatch.setattr(update, "check", refuse)

    async def scenario() -> None:
        instance = app.PbApp(repo_root, check_updates=False)
        async with instance.run_test() as pilot:
            await pilot.pause()
            await pilot.pause(0.2)
            assert not isinstance(instance.screen, UpdatePrompt)

    drive(scenario)


def test_a_clone_is_told_to_git_pull_rather_than_offered_an_install(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pb installed with `-e` is a checkout; installing over it is not pb's."""
    monkeypatch.setattr(update, "check", lambda current, **kw: update.Result(RELEASE, True))
    monkeypatch.setattr(update, "install_method", lambda *a, **k: "source")

    async def scenario() -> None:
        instance = app.PbApp(repo_root)
        async with instance.run_test() as pilot:
            assert await settle(pilot, lambda: isinstance(instance.screen, UpdatePrompt))
            prompt = instance.screen
            assert isinstance(prompt, UpdatePrompt)
            assert await settle(pilot, lambda: bool(prompt.query("#update")))
            assert prompt._command == ""
            assert "git" in prompt._note
            assert prompt.query_one("#update", Button).disabled
            # ...and skipping still works from a prompt that cannot install.
            await press(pilot, prompt, "#skip")
            await pilot.pause()
            assert not isinstance(instance.screen, UpdatePrompt)
        assert update.load_state()["skipped"] == "0.2.0"

    drive(scenario)
