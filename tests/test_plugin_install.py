"""Installing from GitHub — exercised against a local git repository.

`owner/repo` resolves to a github.com URL, and everything after that is git
cloning a URL. A repository on disk is such a URL, so the whole install,
update, pin and remove path runs here without a network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pb.plugins import manage, source
from pb.plugins.manifest import ManifestError
from pb.plugins.store import Store, StoreError

# --- what the user typed -------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "url", "ref"),
    [
        ("owner/pb-x", "https://github.com/owner/pb-x.git", ""),
        ("gh:owner/pb-x", "https://github.com/owner/pb-x.git", ""),
        ("github:owner/pb-x", "https://github.com/owner/pb-x.git", ""),
        ("github.com/owner/pb-x", "https://github.com/owner/pb-x.git", ""),
        ("https://github.com/owner/pb-x", "https://github.com/owner/pb-x", ""),
        ("owner/pb-x@v1.2.3", "https://github.com/owner/pb-x.git", "v1.2.3"),
        ("gh:owner/pb-x@main", "https://github.com/owner/pb-x.git", "main"),
        ("git@github.com:owner/pb-x.git", "git@github.com:owner/pb-x.git", ""),
        ("https://gitlab.example/a/b.git", "https://gitlab.example/a/b.git", ""),
        ("https://gitlab.example/a/b.git#tag", "https://gitlab.example/a/b.git", "tag"),
        ("ssh://git@host/a/b", "ssh://git@host/a/b", ""),
    ],
)
def test_a_source_resolves_to_a_git_url(spec: str, url: str, ref: str) -> None:
    resolved = source.resolve(spec)
    assert resolved.url == url
    assert resolved.ref == ref
    assert resolved.spec == spec


def test_an_explicit_ref_beats_the_one_in_the_spec() -> None:
    assert source.resolve("owner/pb-x@v1", ref="v2").ref == "v2"


def test_the_name_hint_is_the_repository_name() -> None:
    assert source.resolve("owner/pb-x").name_hint == "pb-x"
    assert source.resolve("git@github.com:owner/pb-x.git").name_hint == "pb-x"


@pytest.mark.parametrize("spec", ["", "   ", "not a source!", "one/two/three/four/five"])
def test_something_that_is_not_a_source_says_so(spec: str) -> None:
    with pytest.raises(source.SourceError):
        source.resolve(spec)


def test_a_directory_that_is_not_a_repository_is_refused(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(source.SourceError, match="not a git repository"):
        source.resolve(str(plain))


# --- installing ------------------------------------------------------------


def test_installing_clones_the_repo_and_records_the_commit(
    store: Store, plugin_git_repo
) -> None:
    upstream = plugin_git_repo()
    done = manage.install(store, str(upstream))

    assert done.record.name == "pb-probe"
    assert done.record.version == "1.0"
    assert len(done.record.commit) == 40
    assert (store.dir_for("pb-probe") / "pb-plugin.toml").is_file()
    assert store.get("pb-probe").enabled is True


def test_the_name_comes_from_the_manifest_not_the_repository_directory(
    store: Store, plugin_git_repo
) -> None:
    """A repo called anything still installs under the name it declares."""
    upstream = plugin_git_repo(name="pb-probe")
    renamed = upstream.parent / "some-checkout"
    upstream.rename(renamed)
    done = manage.install(store, str(renamed))
    assert done.record.name == "pb-probe"


def test_a_name_that_disagrees_with_the_manifest_is_refused(
    store: Store, plugin_git_repo
) -> None:
    upstream = plugin_git_repo()
    with pytest.raises(ManifestError, match="calls itself"):
        manage.install(store, str(upstream), name="pb-something-else")
    assert store.records() == []
    assert not store.dir_for("pb-something-else").exists()


def test_installing_something_without_a_manifest_leaves_nothing_behind(
    store: Store, tmp_path: Path, git
) -> None:
    bare = tmp_path / "not-a-plugin"
    (bare / "src").mkdir(parents=True)
    (bare / "src" / "x.py").write_text("x = 1\n")
    git(bare, "init", "-q", "-b", "main")
    git(bare, "add", "-A")
    git(bare, "commit", "-qm", "Initial")

    with pytest.raises(ManifestError):
        manage.install(store, str(bare))
    assert store.records() == []
    assert list(store.plugins_dir.glob("*")) == []


def test_installing_twice_is_refused_unless_forced(store: Store, plugin_git_repo) -> None:
    upstream = plugin_git_repo()
    manage.install(store, str(upstream))
    with pytest.raises(StoreError, match="already installed"):
        manage.install(store, str(upstream))
    # --force replaces it, and keeps the original install date.
    first = store.get("pb-probe").installed
    again = manage.install(store, str(upstream), force=True)
    assert again.record.installed == first


def test_a_ref_that_does_not_exist_leaves_nothing_installed(
    store: Store, plugin_git_repo
) -> None:
    upstream = plugin_git_repo()
    with pytest.raises(source.SourceError):
        manage.install(store, str(upstream), ref="v9.9.9")
    assert store.records() == []
    assert list(store.plugins_dir.glob("*")) == []


# --- updating --------------------------------------------------------------


def test_updating_moves_the_checkout_on(store: Store, plugin_git_repo, git) -> None:
    upstream = plugin_git_repo()
    first = manage.install(store, str(upstream))

    (upstream / "pb_probe.py").write_text("VERSION = 2\n")
    (upstream / "pb-plugin.toml").write_text(
        '[plugin]\nname = "pb-probe"\nversion = "2.0"\napi = 1\nmodule = "pb_probe"\n'
    )
    git(upstream, "add", "-A")
    git(upstream, "commit", "-qm", "Second")

    done = manage.update(store, "pb-probe")
    assert done.changed
    assert done.previous_commit == first.record.commit
    assert done.record.version == "2.0"
    assert "VERSION = 2" in (store.dir_for("pb-probe") / "pb_probe.py").read_text()


def test_updating_when_there_is_nothing_new_says_so(store: Store, plugin_git_repo) -> None:
    upstream = plugin_git_repo()
    manage.install(store, str(upstream))
    assert manage.update(store, "pb-probe").changed is False


def test_a_pinned_plugin_stays_pinned_over_an_update(
    store: Store, plugin_git_repo, git
) -> None:
    upstream = plugin_git_repo()
    git(upstream, "tag", "v1.0.0")
    pinned = manage.install(store, str(upstream), ref="v1.0.0")

    (upstream / "later.txt").write_text("after the tag\n")
    git(upstream, "add", "-A")
    git(upstream, "commit", "-qm", "After the tag")

    done = manage.update(store, "pb-probe")
    assert done.record.commit == pinned.record.commit
    assert not (store.dir_for("pb-probe") / "later.txt").exists()


def test_updating_all_skips_a_linked_plugin(store: Store, plugin_git_repo, linked_plugin) -> None:
    manage.install(store, str(plugin_git_repo(name="pb-probe")))
    linked_plugin(name="pb-mine", module="pb_mine")
    done, failed = manage.update_all(store)
    assert [d.record.name for d in done] == ["pb-probe"]
    assert failed == []


def test_updating_a_linked_plugin_by_name_explains_why_not(
    store: Store, linked_plugin
) -> None:
    linked_plugin(name="pb-mine", module="pb_mine")
    with pytest.raises(StoreError, match="working copy"):
        manage.update(store, "pb-mine")


def test_updating_something_never_installed_raises(store: Store) -> None:
    with pytest.raises(StoreError, match="not installed"):
        manage.update(store, "pb-absent")


def test_an_install_whose_directory_vanished_asks_to_be_reinstalled(
    store: Store, plugin_git_repo
) -> None:
    manage.install(store, str(plugin_git_repo()))
    store.remove_tree("pb-probe")
    with pytest.raises(StoreError, match="reinstall"):
        manage.update(store, "pb-probe")


# --- linking and removing ---------------------------------------------------


def test_linking_reads_the_checkout_where_it_lies(store: Store, make_plugin) -> None:
    root = make_plugin(name="pb-mine", module="pb_mine")
    done = manage.link(store, root)
    assert done.record.linked
    assert done.record.path == str(root)
    assert store.root_for(done.record) == root
    # Nothing was copied into the store.
    assert not store.dir_for("pb-mine").exists()


def test_linking_over_a_git_install_is_refused(store: Store, plugin_git_repo) -> None:
    upstream = plugin_git_repo()
    manage.install(store, str(upstream))
    with pytest.raises(StoreError, match="already installed"):
        manage.link(store, upstream)


def test_linking_a_directory_with_no_plugin_in_it_raises(store: Store, tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        manage.link(store, tmp_path)


def test_removing_deletes_an_installed_checkout(store: Store, plugin_git_repo) -> None:
    manage.install(store, str(plugin_git_repo()))
    manage.remove(store, "pb-probe")
    assert store.records() == []
    assert not store.dir_for("pb-probe").exists()


def test_removing_a_linked_plugin_leaves_your_files_alone(
    store: Store, make_plugin
) -> None:
    root = make_plugin(name="pb-mine", module="pb_mine")
    manage.link(store, root)
    manage.remove(store, "pb-mine")
    assert store.records() == []
    assert (root / "pb-plugin.toml").is_file()


def test_describe_reports_what_is_checked_out(store: Store, plugin_git_repo) -> None:
    manage.install(store, str(plugin_git_repo()))
    fields = manage.describe(store, "pb-probe")
    assert fields["name"] == "pb-probe"
    assert fields["state"] == "enabled"
    assert fields["exists"] == "yes"
    assert fields["module"] == "pb_probe"
    assert "Initial" in fields["checked out"]
