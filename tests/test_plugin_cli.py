"""`pb plugin …` — the command line, and what it refuses to do.

Installing runs third-party code later, so the interesting cases are the
refusals: no confirmation, no terminal, nothing installed under that name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pb import app
from pb.plugins import cli
from pb.plugins.store import Store


def run(*argv: str) -> int:
    return cli.main(list(argv))


def test_no_subcommand_prints_the_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert run() == 0
    assert "install" in capsys.readouterr().out


def test_pb_plugin_is_dispatched_before_the_repo_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`pb plugin list` must not be read as `pb <path>`."""
    monkeypatch.setattr("sys.argv", ["pb", "plugin", "list"])
    assert app.main() == 0
    assert "No plugins installed" in capsys.readouterr().out


def test_list_says_how_to_get_started_when_there_is_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run("list") == 0
    out = capsys.readouterr().out
    assert "No plugins installed" in out
    assert "pb plugin install owner/repo" in out


def test_list_shows_the_commit_and_the_source(
    plugin_git_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    upstream = plugin_git_repo()
    assert run("install", str(upstream), "--yes") == 0
    capsys.readouterr()

    assert run("list") == 0
    out = capsys.readouterr().out
    assert "pb-probe" in out
    assert "1.0" in out
    assert str(upstream) in out


def test_paths_shows_where_a_plugin_lives(
    plugin_git_repo, store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    run("install", str(plugin_git_repo()), "--yes")
    capsys.readouterr()
    assert run("list", "--paths") == 0
    assert str(store.dir_for("pb-probe")) in capsys.readouterr().out


def test_installing_warns_what_a_plugin_can_do(
    plugin_git_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("install", str(plugin_git_repo()), "--yes") == 0
    out = capsys.readouterr().out
    assert "runs inside pb, with your permissions" in out
    assert "Installed pb-probe" in out


def test_installing_without_a_terminal_refuses_rather_than_hanging(
    plugin_git_repo, store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    """capsys leaves stdin not a tty, which is the CI and script case."""
    assert run("install", str(plugin_git_repo())) == 1
    assert "Pass --yes" in capsys.readouterr().err
    assert store.records() == []


def test_declining_at_the_prompt_installs_nothing(
    plugin_git_repo, store: Store, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    assert run("install", str(plugin_git_repo())) == 1
    assert "Nothing was installed" in capsys.readouterr().out
    assert store.records() == []


def test_accepting_at_the_prompt_installs(
    plugin_git_repo, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    assert run("install", str(plugin_git_repo())) == 0
    assert store.get("pb-probe") is not None


def test_a_source_that_makes_no_sense_is_a_message_not_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run("install", "not a source!", "--yes") == 1
    assert "is not a plugin source" in capsys.readouterr().err


def test_installing_something_that_is_not_a_plugin_fails_cleanly(
    tmp_path: Path, git, store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    bare = tmp_path / "empty-repo"
    bare.mkdir()
    (bare / "README.md").write_text("nothing to see\n")
    git(bare, "init", "-q", "-b", "main")
    git(bare, "add", "-A")
    git(bare, "commit", "-qm", "Initial")

    assert run("install", str(bare), "--yes") == 1
    assert "pb-plugin.toml" in capsys.readouterr().err
    assert store.records() == []


def test_update_reports_the_move(
    plugin_git_repo, git, capsys: pytest.CaptureFixture[str]
) -> None:
    upstream = plugin_git_repo()
    run("install", str(upstream), "--yes")
    capsys.readouterr()

    (upstream / "extra.txt").write_text("more\n")
    git(upstream, "add", "-A")
    git(upstream, "commit", "-qm", "Second")

    assert run("update") == 0
    out = capsys.readouterr().out
    assert "→" in out
    assert "Restart pb" in out


def test_update_with_nothing_installed_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    assert run("update") == 0
    assert "Nothing to update" in capsys.readouterr().out


def test_update_of_an_unknown_plugin_is_an_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run("update", "pb-absent") == 1
    assert "not installed" in capsys.readouterr().err


def test_enable_and_disable_are_written_down(
    plugin_git_repo, store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    run("install", str(plugin_git_repo()), "--yes")
    assert run("disable", "pb-probe") == 0
    assert store.get("pb-probe").enabled is False
    assert run("enable", "pb-probe") == 0
    assert store.get("pb-probe").enabled is True


def test_remove_deletes_the_checkout(
    plugin_git_repo, store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    run("install", str(plugin_git_repo()), "--yes")
    assert run("remove", "pb-probe") == 0
    assert "removed" in capsys.readouterr().out
    assert not store.dir_for("pb-probe").exists()


def test_link_registers_a_working_copy(
    make_plugin, store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_plugin(name="pb-mine", module="pb_mine")
    assert run("link", str(root)) == 0
    out = capsys.readouterr().out
    assert "Linked pb-mine" in out
    assert store.get("pb-mine").linked


def test_new_writes_a_plugin_that_loads(
    tmp_path: Path, store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    """The scaffold is the documentation, so it has to actually work."""
    assert run("new", "pb-example", "--dir", str(tmp_path)) == 0
    root = tmp_path / "pb-example"
    assert (root / "pb-plugin.toml").is_file()
    assert (root / "pb_example" / "__init__.py").is_file()

    assert run("link", str(root)) == 0
    capsys.readouterr()
    assert run("doctor") == 0
    out = capsys.readouterr().out
    assert "✔ pb-example" in out
    assert "tabs" in out


def test_new_refuses_a_name_that_is_not_usable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("new", "Not A Name", "--dir", str(tmp_path)) == 1
    assert "not a usable plugin name" in capsys.readouterr().err


def test_new_refuses_to_write_over_something(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    existing = tmp_path / "pb-example"
    existing.mkdir()
    (existing / "mine.py").write_text("keep me\n")
    assert run("new", "pb-example", "--dir", str(tmp_path)) == 1
    assert "already exists" in capsys.readouterr().err
    assert (existing / "mine.py").read_text() == "keep me\n"


def test_doctor_reports_a_plugin_that_will_not_import(
    linked_plugin, capsys: pytest.CaptureFixture[str]
) -> None:
    linked_plugin(name="pb-bad", module="pb_bad", body="raise RuntimeError('boom')")
    assert run("doctor") == 1
    out = capsys.readouterr().out
    assert "✘ pb-bad" in out
    assert "boom" in out
    # The traceback is there too — it is the useful half when developing.
    assert "RuntimeError" in out


def test_doctor_says_which_api_it_speaks(capsys: pytest.CaptureFixture[str]) -> None:
    from pb.plugins.api import API_VERSION

    assert run("doctor") == 0
    assert f"plugin API      {API_VERSION}" in capsys.readouterr().out


def test_doctor_marks_a_disabled_plugin_rather_than_loading_it(
    linked_plugin, store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    linked_plugin(name="pb-bad", module="pb_bad", body="raise RuntimeError('boom')")
    store.set_enabled("pb-bad", False)
    assert run("doctor") == 0
    assert "- pb-bad" in capsys.readouterr().out


def test_info_names_the_hooks_and_the_commit(
    plugin_git_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    run("install", str(plugin_git_repo()), "--yes")
    capsys.readouterr()
    assert run("info", "pb-probe") == 0
    out = capsys.readouterr().out
    assert "module" in out
    assert "pb_probe" in out
    assert "Initial" in out


def test_info_about_nothing_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert run("info", "pb-absent") == 1
    assert "not installed" in capsys.readouterr().err


def test_path_prints_the_plugin_directory(
    store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("path") == 0
    assert capsys.readouterr().out.strip() == str(store.plugins_dir)


def test_the_no_plugins_flag_is_documented(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["pb", "--help"])
    with pytest.raises(SystemExit):
        app.main()
    out = capsys.readouterr().out
    assert "--no-plugins" in out
    assert "pb plugin" in out
