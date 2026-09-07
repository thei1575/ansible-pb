"""The record of what is installed.

The state file is the source of truth, so the tests are about it surviving:
being unreadable, being written to twice, and never being allowed to point at
a directory outside the store.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pb.plugins.store import Record, Store, StoreError, config_dir


def test_the_config_directory_follows_pb_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PB_HOME", "/tmp/somewhere")
    assert config_dir() == Path("/tmp/somewhere")


def test_without_pb_home_it_follows_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PB_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg")
    assert config_dir() == Path("/tmp/xdg/pb")


def test_without_either_it_is_under_the_home_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PB_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert config_dir() == Path.home() / ".config" / "pb"


def test_nothing_installed_is_an_empty_list_not_an_error(store: Store) -> None:
    assert store.records() == []
    assert store.get("pb-nothing") is None


def test_a_record_survives_a_round_trip(store: Store) -> None:
    store.put(Record(name="pb-a", source="owner/pb-a", commit="a" * 40, ref="v1"))
    (record,) = store.records()
    assert record.name == "pb-a"
    assert record.short_commit == "aaaaaaa"
    assert record.ref == "v1"
    assert record.enabled is True
    assert record.linked is False


def test_putting_the_same_name_twice_replaces_it_and_keeps_the_order(store: Store) -> None:
    store.put(Record(name="pb-a"))
    store.put(Record(name="pb-b"))
    store.put(Record(name="pb-a", version="2"))
    assert [(r.name, r.version) for r in store.records()] == [("pb-a", "2"), ("pb-b", "")]


def test_disabling_leaves_the_record_in_place(store: Store) -> None:
    store.put(Record(name="pb-a"))
    assert store.set_enabled("pb-a", False).enabled is False
    assert store.get("pb-a").enabled is False
    assert store.set_enabled("pb-a", True).enabled is True


def test_asking_about_something_not_installed_raises(store: Store) -> None:
    with pytest.raises(StoreError, match="not installed"):
        store.require("pb-absent")


def test_dropping_forgets_only_that_one(store: Store) -> None:
    store.put(Record(name="pb-a"))
    store.put(Record(name="pb-b"))
    store.drop("pb-a")
    assert [r.name for r in store.records()] == ["pb-b"]


def test_an_unreadable_state_file_reads_as_nothing_installed(store: Store) -> None:
    """A corrupt file must not stop pb from starting."""
    store.root.mkdir(parents=True, exist_ok=True)
    store.state_file.write_text("{not json")
    assert store.records() == []


def test_entries_pb_does_not_understand_are_skipped(store: Store) -> None:
    """A state file written by a newer pb must still load what it can."""
    store.root.mkdir(parents=True, exist_ok=True)
    store.state_file.write_text(
        json.dumps(
            {
                "version": 99,
                "plugins": [
                    {"name": "pb-a", "unknown_field": True},
                    {"no_name": 1},
                    "not a table",
                ],
            }
        )
    )
    assert [r.name for r in store.records()] == ["pb-a"]


def test_a_linked_record_is_read_where_it_lies(store: Store, tmp_path: Path) -> None:
    elsewhere = tmp_path / "my-checkout"
    elsewhere.mkdir()
    record = store.put(Record(name="pb-a", path=str(elsewhere)))
    assert record.linked
    assert store.root_for(record) == elsewhere
    assert store.root_for(Record(name="pb-b")) == store.dir_for("pb-b")


def test_deleting_a_tree_refuses_to_leave_the_store(store: Store) -> None:
    with pytest.raises(StoreError, match="refusing to delete"):
        store.remove_tree("../../elsewhere")


def test_each_plugin_gets_its_own_data_directory(store: Store) -> None:
    assert store.data_dir_for("pb-a") != store.data_dir_for("pb-b")
    assert store.root in store.data_dir_for("pb-a").parents
