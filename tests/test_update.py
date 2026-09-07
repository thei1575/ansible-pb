"""The update check: versions, changelogs, skip state and install commands.

Nothing here goes near a network. The two functions that would - `_get` and
`latest_release` - are replaced; everything else is pure and gets a real test.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from pb import update

CHANGELOG = """\
# Changelog

All notable changes to pb are recorded here.

## [Unreleased]

### Added

* Something not released yet.

## [0.3.0] - 2026-03-01

### Added

* A third thing.

## [0.2.0] - 2026-02-01

### Fixed

* A second thing.

## [0.1.0] - 2026-01-01

### Added

* The first thing.
"""


# --- versions --------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0.1.0", (0, 1, 0, 1, "")),
        ("v0.1.0", (0, 1, 0, 1, "")),
        ("  v1.2.3  ", (1, 2, 3, 1, "")),
        ("2", (2, 0, 0, 1, "")),
        ("2.1", (2, 1, 0, 1, "")),
        ("0.2.0rc1", (0, 2, 0, 0, "rc1")),
    ],
)
def test_a_version_parses_to_a_comparable_tuple(text: str, expected: tuple) -> None:
    assert update.parse_version(text) == expected


@pytest.mark.parametrize("text", ["", "Unreleased", "main", "latest", "v"])
def test_what_is_not_a_version_parses_to_nothing(text: str) -> None:
    assert update.parse_version(text) is None


@pytest.mark.parametrize(
    ("candidate", "current"),
    [("0.2.0", "0.1.0"), ("v0.2.0", "0.1.0"), ("1.0.0", "0.9.9"), ("0.10.0", "0.9.0")],
)
def test_a_higher_version_is_newer(candidate: str, current: str) -> None:
    assert update.is_newer(candidate, current)


@pytest.mark.parametrize(
    ("candidate", "current"),
    [
        ("0.1.0", "0.1.0"),
        ("0.1.0", "0.2.0"),
        ("0.9.0", "0.10.0"),
        # A pre-release is below the release it leads to, not above it.
        ("0.2.0rc1", "0.2.0"),
        ("Unreleased", "0.1.0"),
        ("0.2.0", "not-a-version"),
    ],
)
def test_anything_else_is_not_newer(candidate: str, current: str) -> None:
    assert not update.is_newer(candidate, current)


# --- release notes ---------------------------------------------------


def test_the_changelog_is_cut_at_the_version_you_have() -> None:
    notes = update.changelog_since(CHANGELOG, "0.1.0")
    assert "## [0.3.0]" in notes
    assert "## [0.2.0]" in notes
    assert "A third thing." in notes
    assert "A second thing." in notes
    assert "0.1.0" not in notes
    assert "The first thing." not in notes


def test_unreleased_is_not_offered_as_something_you_would_get() -> None:
    notes = update.changelog_since(CHANGELOG, "0.1.0")
    assert "Unreleased" not in notes
    assert "Something not released yet." not in notes


def test_the_preamble_above_the_first_release_is_left_out() -> None:
    assert "All notable changes" not in update.changelog_since(CHANGELOG, "0.1.0")


def test_being_up_to_date_leaves_no_notes() -> None:
    assert update.changelog_since(CHANGELOG, "0.3.0") == ""


def test_notes_come_from_the_tag_and_fall_back_to_main(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tag pushed before the changelog was written on it still has notes."""
    asked: list[str] = []

    def fake_get(url: str, timeout: float, accept: str) -> str | None:
        asked.append(url)
        return None if "v0.3.0" in url else CHANGELOG

    monkeypatch.setattr(update, "_get", fake_get)
    release = update.Release(version="0.3.0", tag="v0.3.0")
    assert "A third thing." in update.release_notes(release, "0.1.0")
    assert [u.split("/ansible-pb/")[1].split("/")[0] for u in asked] == ["v0.3.0", "main"]


# --- what GitHub says ------------------------------------------------


def test_a_published_release_is_read_off_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps(
        {
            "tag_name": "v0.2.0",
            "body": "  Fixed the thing.  ",
            "html_url": "https://example.invalid/r/v0.2.0",
        }
    )
    monkeypatch.setattr(update, "_get", lambda url, timeout, accept: body)
    release = update.latest_release()
    assert release is not None
    assert (release.version, release.tag) == ("0.2.0", "v0.2.0")
    assert release.notes == "Fixed the thing."
    assert release.url == "https://example.invalid/r/v0.2.0"


def test_a_repo_with_tags_but_no_release_still_offers_the_newest_tag(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    tags = json.dumps([{"name": "v0.1.0"}, {"name": "v0.10.0"}, {"name": "v0.9.0"}, {}, "junk"])

    def fake_get(url: str, timeout: float, accept: str) -> str | None:
        return None if "releases/latest" in url else tags

    monkeypatch.setattr(update, "_get", fake_get)
    release = update.latest_release()
    assert release is not None
    assert (release.version, release.tag) == ("0.10.0", "v0.10.0")


def test_being_offline_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update, "_get", lambda url, timeout, accept: None)
    assert update.latest_release() is None


def test_a_body_that_is_not_json_is_not_a_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update, "_get", lambda url, timeout, accept: "<html>rate limited</html>")
    assert update.latest_release() is None


# --- state -----------------------------------------------------------


def test_the_state_file_lives_in_pbs_config_directory(tmp_path: Path) -> None:
    """The same directory the plugin store uses - one place, one rule."""
    assert update.state_path() == tmp_path / "pb-home" / "update.json"


def test_the_state_file_falls_back_to_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PB_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert update.state_path() == tmp_path / "config" / "pb" / "update.json"


def test_a_skip_survives_being_written_and_read_back() -> None:
    update.skip("0.2.0")
    assert update.load_state()["skipped"] == "0.2.0"
    update.forget_skip()
    assert "skipped" not in update.load_state()


def test_an_unreadable_state_file_reads_as_no_state() -> None:
    path = update.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert update.load_state() == {}


def test_a_state_file_that_is_not_an_object_reads_as_no_state() -> None:
    path = update.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2]", encoding="utf-8")
    assert update.load_state() == {}


def test_a_check_is_due_when_none_was_ever_made() -> None:
    assert update.due({}, now=1000.0)
    assert update.due({"last_check": "yesterday"}, now=1000.0)


def test_a_check_is_not_due_again_the_same_day() -> None:
    now = 1_000_000.0
    assert not update.due({"last_check": now - 60}, now=now)
    assert update.due({"last_check": now - update.CHECK_EVERY - 1}, now=now)


def test_a_clock_that_went_backwards_does_not_park_the_check() -> None:
    now = 1_000_000.0
    assert update.due({"last_check": now + 99_999}, now=now)


@pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE", "on"])
def test_the_opt_out_turns_the_check_off(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("PB_NO_UPDATE_CHECK", value)
    assert update.disabled()


@pytest.mark.parametrize("value", ["", "0", "false", "no", "  "])
def test_an_empty_or_negative_opt_out_leaves_it_on(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("PB_NO_UPDATE_CHECK", value)
    assert not update.disabled()


# --- the check -------------------------------------------------------


def _release(version: str = "0.2.0") -> update.Release:
    return update.Release(version=version, tag=f"v{version}", notes="something")


def test_a_newer_version_comes_back_with_its_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update, "latest_release", lambda timeout: _release())
    result = update.check("0.1.0")
    assert result.checked
    assert result.release is not None
    assert result.release.version == "0.2.0"


def test_the_check_records_when_it_last_ran(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update, "latest_release", lambda timeout: _release())
    update.check("0.1.0", now=1234.0)
    assert update.load_state()["last_check"] == 1234.0


def test_a_second_check_the_same_day_does_not_go_out_again(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def fake_latest(timeout: float) -> update.Release:
        calls.append(timeout)
        return _release()

    monkeypatch.setattr(update, "latest_release", fake_latest)
    assert update.check("0.1.0", now=1000.0).release is not None
    assert update.check("0.1.0", now=1060.0) == update.Result()
    assert len(calls) == 1


def test_the_version_you_are_on_is_not_offered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update, "latest_release", lambda timeout: _release("0.2.0"))
    result = update.check("0.2.0")
    assert result.checked and result.release is None and not result.error


def test_a_skipped_version_is_never_offered_again(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update, "latest_release", lambda timeout: _release("0.2.0"))
    update.skip("0.2.0")
    assert update.check("0.1.0", now=1000.0).release is None
    # ...but a later release is a different question.
    monkeypatch.setattr(update, "latest_release", lambda timeout: _release("0.3.0"))
    assert update.check("0.1.0", now=1_000_000.0).release is not None


def test_asking_for_it_ignores_the_interval_the_skip_and_the_opt_out(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PB_NO_UPDATE_CHECK", "1")
    monkeypatch.setattr(update, "latest_release", lambda timeout: _release("0.2.0"))
    update.skip("0.2.0")
    update.save_state({**update.load_state(), "last_check": time.time()})
    assert update.check("0.1.0", force=True).release is not None


def test_the_opt_out_stops_the_automatic_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PB_NO_UPDATE_CHECK", "1")
    monkeypatch.setattr(
        update, "latest_release", lambda timeout: pytest.fail("went to the network")
    )
    assert update.check("0.1.0") == update.Result()


def test_being_unable_to_reach_github_is_reported_not_raised(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update, "latest_release", lambda timeout: None)
    result = update.check("0.1.0")
    assert result.checked and result.release is None
    assert "github.com" in result.error


def test_a_release_with_no_body_gets_its_notes_from_the_changelog(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        update, "latest_release", lambda timeout: update.Release("0.3.0", "v0.3.0")
    )
    monkeypatch.setattr(update, "_get", lambda url, timeout, accept: CHANGELOG)
    result = update.check("0.1.0")
    assert result.release is not None
    assert "A third thing." in result.release.notes


# --- installing it ---------------------------------------------------


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        ("/home/me/.local/share/uv/tools/ansible-pb", "uv"),
        ("/home/me/.local/share/pipx/venvs/ansible-pb", "pipx"),
        ("/home/me/.local/pipx/venvs/ansible-pb", "pipx"),
    ],
)
def test_the_installer_is_read_off_where_pb_lives(prefix: str, expected: str) -> None:
    assert update.install_method(Path(prefix)) == expected


def test_a_plain_virtualenv_is_a_pip_install() -> None:
    assert (
        update.install_method(
            Path("/home/me/venv"), Path("/home/me/venv/lib/python3.13/site-packages/pb")
        )
        == "pip"
    )


def test_a_checkout_is_updated_with_git_not_by_pb() -> None:
    """An editable install leaves pb outside site-packages."""
    assert update.install_method(Path("/home/me/venv"), Path("/home/me/src/ansible-pb/src/pb")) == (
        "source"
    )
    upgrade = update.upgrade_command("v0.2.0", "source")
    assert not upgrade.possible
    assert "git" in upgrade.manual


@pytest.mark.parametrize(
    ("method", "head"),
    [("uv", ["uv", "tool", "install", "--force"]), ("pipx", ["pipx", "install", "--force"])],
)
def test_the_install_command_pins_the_tag(method: str, head: list[str]) -> None:
    upgrade = update.upgrade_command("v0.2.0", method)
    assert upgrade.possible
    assert upgrade.argv[: len(head)] == head
    assert upgrade.argv[-1] == f"{update.GIT_URL}@v0.2.0"


def test_the_pip_command_upgrades_this_interpreter() -> None:
    import sys

    upgrade = update.upgrade_command("v0.2.0", "pip")
    assert upgrade.argv[:4] == [sys.executable, "-m", "pip", "install"]
    assert upgrade.argv[-1] == f"{update.GIT_URL}@v0.2.0"


def test_every_install_method_has_a_name_for_doctor() -> None:
    for method in ("uv", "pipx", "pip", "source"):
        assert update.install_label(method)
