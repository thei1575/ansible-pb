"""The command line, up to the point where the TUI would start.

The two paths worth testing are the refusals: pb has to say why it will not
start rather than opening an empty console.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pb
from pb import app


def test_version_is_a_release_number() -> None:
    assert pb.__version__.count(".") >= 1


def test_version_flag_prints_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["pb", "--version"])
    with pytest.raises(SystemExit) as exc:
        app.main()
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"pb {pb.__version__}"


def test_a_path_that_is_not_a_directory_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    a_file = tmp_path / "ansible.cfg"
    a_file.write_text("[defaults]\n")
    monkeypatch.setattr("sys.argv", ["pb", str(a_file)])
    assert app.main() == 2
    assert "is not a directory" in capsys.readouterr().err


def test_a_directory_with_no_ansible_cfg_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.argv", ["pb", str(tmp_path)])
    assert app.main() == 2
    err = capsys.readouterr().err
    assert "no ansible.cfg" in err
    assert str(tmp_path.resolve()) in err


def test_the_stylesheet_ships_with_the_package() -> None:
    """A wheel without pb.tcss starts and then dies on first paint."""
    import importlib.resources as resources

    assert resources.files("pb").joinpath("pb.tcss").is_file()
    assert app.PbApp.CSS_PATH


def test_the_app_is_pointed_at_the_repo_root_it_was_given(repo_root: Path) -> None:
    """Constructing the app must not need a terminal."""
    instance = app.PbApp(repo_root)
    assert instance.repo.root == repo_root
