"""Importing third-party code without letting it take pb down.

Every way a plugin can be broken should come back as a `Failure` naming the
plugin and the stage it failed at - never as an exception out of `load_all`.
"""

from __future__ import annotations

from pathlib import Path

from pb.plugins import loader
from pb.plugins.api import API_VERSION, Plugin
from pb.plugins.store import Record, Store

WORKS = """\
from pb.plugins import Plugin


class Mine(Plugin):
    def activate(self):
        pass
"""


def test_nothing_installed_loads_nothing(store: Store) -> None:
    loaded = loader.load_all(store)
    assert loaded.plugins == []
    assert loaded.failures == []


def test_a_working_plugin_comes_back_with_its_manifest_filled_in(
    store: Store, linked_plugin
) -> None:
    root = linked_plugin(name="pb-mine", module="pb_mine", body=WORKS, version="3.1")
    loaded = loader.load_all(store)

    assert loaded.failures == []
    (plugin,) = loaded.plugins
    assert isinstance(plugin, Plugin)
    assert plugin.name == "pb-mine"
    assert plugin.version == "3.1"
    assert plugin.summary == "a test plugin"
    assert plugin.root == root
    assert plugin.data_dir == store.data_dir_for("pb-mine")


def test_a_disabled_plugin_is_not_imported(store: Store, linked_plugin) -> None:
    linked_plugin(name="pb-mine", module="pb_mine", body="raise RuntimeError('boom')")
    store.set_enabled("pb-mine", False)
    loaded = loader.load_all(store)
    assert loaded.plugins == []
    assert loaded.failures == []
    # Still on the list, so the Plugins tab can offer to enable it again.
    assert [r.name for r in loaded.records.values()] == ["pb-mine"]


def test_a_plugin_that_raises_on_import_is_reported_with_its_traceback(
    store: Store, linked_plugin
) -> None:
    linked_plugin(name="pb-mine", module="pb_mine", body="raise RuntimeError('boom')")
    loaded = loader.load_all(store)

    assert loaded.plugins == []
    (failure,) = loaded.failures
    assert failure.name == "pb-mine"
    assert failure.stage == "import"
    assert "boom" in failure.message
    assert "RuntimeError" in failure.detail


def test_a_plugin_that_defines_no_plugin_class_is_reported(
    store: Store, linked_plugin
) -> None:
    linked_plugin(name="pb-mine", module="pb_mine", body="ANSWER = 42\n")
    (failure,) = loader.load_all(store).failures
    assert failure.stage == "entry-point"
    assert "pb_mine" in failure.message


def test_a_constructor_that_raises_is_reported(store: Store, linked_plugin) -> None:
    linked_plugin(
        name="pb-mine",
        module="pb_mine",
        body=(
            "from pb.plugins import Plugin\n\n\n"
            "class Mine(Plugin):\n"
            "    def __init__(self):\n"
            "        raise ValueError('no')\n"
        ),
    )
    (failure,) = loader.load_all(store).failures
    assert failure.stage == "construct"
    assert "ValueError" in failure.message


def test_a_plugin_written_for_another_api_never_gets_imported(
    store: Store, make_plugin
) -> None:
    """The gate has to hold for a plugin already in the state file - one whose
    manifest changed under pb, or that a newer pb installed."""
    root = make_plugin(
        name="pb-mine",
        manifest=f'[plugin]\nname = "pb-mine"\napi = {API_VERSION + 1}\nmodule = "pb_mine"\n',
        body="raise RuntimeError('this must never run')",
    )
    store.put(Record(name="pb-mine", path=str(root)))

    (failure,) = loader.load_all(store).failures
    assert failure.stage == "manifest"
    assert "plugin API" in failure.message


def test_a_linked_directory_that_moved_says_so(store: Store, linked_plugin) -> None:
    import shutil

    root = linked_plugin(name="pb-mine", module="pb_mine", body=WORKS)
    shutil.rmtree(root)
    (failure,) = loader.load_all(store).failures
    assert failure.stage == "manifest"
    assert "linked directory moved" in failure.message


def test_a_plugin_renamed_under_pbs_feet_is_refused(store: Store, linked_plugin) -> None:
    """The name in the state file and the name in the manifest must agree."""
    root = linked_plugin(name="pb-mine", module="pb_mine", body=WORKS)
    (root / "pb-plugin.toml").write_text(
        '[plugin]\nname = "pb-other"\napi = 1\nmodule = "pb_mine"\n'
    )
    (failure,) = loader.load_all(store).failures
    assert "calls itself" in failure.message


def test_two_plugins_cannot_claim_the_same_module_name(
    store: Store, linked_plugin
) -> None:
    linked_plugin(name="pb-one", module="pb_shared", body=WORKS)
    linked_plugin(name="pb-two", module="pb_shared", body=WORKS)
    loaded = loader.load_all(store)

    assert [p.name for p in loaded.plugins] == ["pb-one"]
    (failure,) = loaded.failures
    assert failure.name == "pb-two"
    assert "pb-one already uses" in failure.message


def test_a_broken_plugin_does_not_stop_the_next_one_loading(
    store: Store, linked_plugin
) -> None:
    linked_plugin(name="pb-bad", module="pb_bad", body="raise RuntimeError('boom')")
    linked_plugin(name="pb-good", module="pb_good", body=WORKS)
    loaded = loader.load_all(store)

    assert [p.name for p in loaded.plugins] == ["pb-good"]
    assert [f.name for f in loaded.failures] == ["pb-bad"]


def test_plugins_load_in_the_order_they_were_installed(
    store: Store, linked_plugin
) -> None:
    """Order decides who wins when two plugins replace the same action."""
    for name in ("pb-c", "pb-a", "pb-b"):
        linked_plugin(name=name, module=name.replace("-", "_"), body=WORKS)
    assert [p.name for p in loader.load_all(store).plugins] == ["pb-c", "pb-a", "pb-b"]


def test_an_explicit_entry_point_wins_over_scanning(store: Store, linked_plugin) -> None:
    linked_plugin(
        name="pb-mine",
        module="pb_mine",
        body=(
            "from pb.plugins import Plugin\n\n\n"
            "class NotThisOne(Plugin):\n    pass\n\n\n"
            "class ThisOne(Plugin):\n    pass\n\n\n"
            "PB_PLUGIN = ThisOne\n"
        ),
    )
    (plugin,) = loader.load_all(store).plugins
    assert type(plugin).__name__ == "ThisOne"


def test_a_plugin_class_imported_from_elsewhere_is_not_instantiated_twice(
    store: Store, linked_plugin
) -> None:
    """Scanning takes what the module defines, not what it imported."""
    linked_plugin(
        name="pb-mine",
        module="pb_mine",
        body=(
            "from pb.plugins import Plugin\n"
            "from pb.plugins.api import Plugin as Alias\n\n\n"
            "class Mine(Plugin):\n    pass\n"
        ),
    )
    assert len(loader.load_all(store).plugins) == 1


def test_stylesheets_are_collected_for_the_app_to_load(
    store: Store, linked_plugin, tmp_path: Path
) -> None:
    root = linked_plugin(
        name="pb-mine",
        manifest=(
            '[plugin]\nname = "pb-mine"\napi = 1\nmodule = "pb_mine"\n'
            'css = ["look.tcss"]\n'
        ),
        body=WORKS,
    )
    (root / "look.tcss").write_text("Static { color: red; }")
    assert loader.load_all(store).css == [root / "look.tcss"]


def test_reloading_the_same_plugin_picks_up_the_new_code(
    store: Store, linked_plugin
) -> None:
    """`pb plugin doctor` and the tests load twice in one process."""
    root = linked_plugin(name="pb-mine", module="pb_mine", body=WORKS)
    assert loader.load_all(store).plugins

    (root / "pb_mine.py").write_text(WORKS.replace("class Mine", "class Renamed"))
    (plugin,) = loader.load_all(store).plugins
    assert type(plugin).__name__ == "Renamed"


def test_check_reports_only_the_problems(store: Store, linked_plugin) -> None:
    linked_plugin(name="pb-good", module="pb_good", body=WORKS)
    linked_plugin(name="pb-bad", module="pb_bad", body="raise RuntimeError('boom')")
    assert [f.name for f in loader.check(store)] == ["pb-bad"]


def test_a_record_the_store_kept_but_the_files_are_gone(store: Store) -> None:
    store.put(Record(name="pb-ghost"))
    (failure,) = loader.load_all(store).failures
    assert failure.stage == "manifest"
    assert "missing" in failure.message
