"""The manifest is the gate: pb reads it before importing anything.

So the tests here are mostly about refusals — a manifest pb cannot make sense
of has to be a message, not a half-loaded plugin.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pb.plugins import manifest as m
from pb.plugins.api import API_VERSION


def test_a_minimal_manifest_needs_only_a_name() -> None:
    parsed = m.parse('[plugin]\nname = "pb-thing"\n')
    assert parsed.name == "pb-thing"
    assert parsed.api == API_VERSION
    assert parsed.python_path == (".",)


def test_the_module_defaults_to_the_name_with_separators_flattened() -> None:
    assert m.parse('[plugin]\nname = "pb-thing.two"\n').import_name == "pb_thing_two"


def test_an_explicit_module_wins() -> None:
    assert m.parse('[plugin]\nname = "pb-a"\nmodule = "somewhere"\n').import_name == "somewhere"


def test_a_plugin_for_another_api_version_is_refused_by_name() -> None:
    with pytest.raises(m.ManifestError) as exc:
        m.parse(f'[plugin]\nname = "pb-old"\napi = {API_VERSION + 1}\n')
    assert "pb-old" in str(exc.value)
    assert str(API_VERSION) in str(exc.value)


@pytest.mark.parametrize(
    "text",
    [
        "name = 'pb-a'",                          # no [plugin] table
        '[plugin]\nname = "Pb Thing"\n',          # spaces and capitals
        '[plugin]\nname = "-leading"\n',
        '[plugin]\nname = ""\n',
        '[plugin]\n',                             # no name at all
        '[plugin]\nname = "pb-a"\napi = "1"\n',   # api is not an integer
        '[plugin]\nname = "pb-a"\nmodule = "not a module"\n',
        '[plugin]\nname = "pb-a"\nversion = 1\n',  # version is not a string
        '[plugin]\nname = "pb-a"\ncss = 3\n',
        "[plugin\nname =",                         # not TOML
    ],
)
def test_a_manifest_pb_cannot_use_raises(text: str) -> None:
    with pytest.raises(m.ManifestError):
        m.parse(text)


@pytest.mark.parametrize("escape", ["/etc/passwd", "../../elsewhere", "a/../../b"])
def test_a_path_that_escapes_the_plugin_is_refused(escape: str) -> None:
    with pytest.raises(m.ManifestError):
        m.parse(f'[plugin]\nname = "pb-a"\npython_path = ["{escape}"]\n')


def test_a_missing_manifest_says_which_file_it_wanted(tmp_path: Path) -> None:
    with pytest.raises(m.ManifestError) as exc:
        m.load(tmp_path)
    assert m.MANIFEST_NAME in str(exc.value)


def test_css_paths_are_absolute_and_skip_what_is_not_there(tmp_path: Path) -> None:
    (tmp_path / "here.tcss").write_text("Static {}")
    parsed = m.parse('[plugin]\nname = "pb-a"\ncss = ["here.tcss", "gone.tcss"]\n')
    assert m.css_paths(tmp_path, parsed) == [tmp_path / "here.tcss"]
