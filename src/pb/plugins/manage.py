"""Install, update, link and remove - the operations behind `pb plugin`.

Kept apart from the CLI so the Plugins tab can run exactly the same code, and
apart from the loader so that installing never imports plugin code: nothing a
plugin ships runs until pb next starts with it enabled.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from . import source
from .manifest import Manifest, ManifestError
from .manifest import load as load_manifest
from .store import Record, Store, StoreError


@dataclass
class Installed:
    """What an install or update did, for the message the user sees."""

    record: Record
    manifest: Manifest
    previous_commit: str = ""

    @property
    def changed(self) -> bool:
        return self.previous_commit != self.record.commit


def install(
    store: Store,
    spec: str,
    ref: str = "",
    name: str = "",
    force: bool = False,
) -> Installed:
    """Clone a plugin and record it.

    The clone lands in a scratch directory first, because the plugin's name
    comes out of its own manifest - pb will not guess it from a repository
    name and then be wrong about it for the life of the install.
    """
    resolved = source.resolve(spec, ref)
    scratch = store.plugins_dir / f".incoming-{os.getpid()}-{int(time.time())}"
    shutil.rmtree(scratch, ignore_errors=True)

    commit = source.clone(resolved, scratch)
    try:
        manifest = load_manifest(scratch)
        plugin_name = name or manifest.name
        if name and name != manifest.name:
            raise ManifestError(
                f"the plugin calls itself {manifest.name!r}, not {name!r}"
            )

        existing = store.get(plugin_name)
        target = store.dir_for(plugin_name)
        if (existing or target.exists()) and not force:
            raise StoreError(
                f"{plugin_name} is already installed - "
                "`pb plugin update` moves it on, or pass --force to replace it"
            )

        if target.exists():
            store.remove_tree(plugin_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        scratch.replace(target)
    except Exception:
        shutil.rmtree(scratch, ignore_errors=True)
        raise

    now = time.time()
    record = store.put(
        Record(
            name=plugin_name,
            source=resolved.spec,
            url=resolved.url,
            ref=resolved.ref,
            commit=commit,
            version=manifest.version,
            summary=manifest.summary,
            enabled=True,
            installed=(existing.installed if existing else now),
            updated=now,
        )
    )
    return Installed(
        record=record,
        manifest=manifest,
        previous_commit=existing.commit if existing else "",
    )


def update(store: Store, name: str) -> Installed:
    """Fetch and move a plugin's checkout on to the newest commit for its ref."""
    record = store.require(name)
    if record.linked:
        raise StoreError(
            f"{name} is linked to {record.path} - it is your working copy, so pb "
            "does not touch it with git"
        )
    root = store.root_for(record)
    if not root.is_dir():
        raise StoreError(f"{name} is recorded but {root} is gone - reinstall it")

    before, after = source.update(root, record.ref)
    manifest = load_manifest(root)
    if manifest.name != name:
        raise ManifestError(
            f"after updating, the plugin calls itself {manifest.name!r} rather than {name!r}"
        )
    record.commit = after
    record.version = manifest.version
    record.summary = manifest.summary
    record.updated = time.time()
    store.put(record)
    return Installed(record=record, manifest=manifest, previous_commit=before)


def update_all(store: Store) -> tuple[list[Installed], list[tuple[str, Exception]]]:
    """Update every git-installed plugin, reporting each failure separately."""
    done: list[Installed] = []
    failed: list[tuple[str, Exception]] = []
    for record in store.records():
        if record.linked:
            continue
        try:
            done.append(update(store, record.name))
        except (StoreError, ManifestError, source.SourceError) as exc:
            failed.append((record.name, exc))
    return done, failed


def link(store: Store, path: str | Path, name: str = "") -> Installed:
    """Register a checkout on disk in place - the development loop.

    pb reads the directory where it is, so an edit is one restart away from
    being live, and `pb plugin update` refuses to touch it.
    """
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise StoreError(f"{root} is not a directory")
    manifest = load_manifest(root)
    plugin_name = name or manifest.name
    if name and name != manifest.name:
        raise ManifestError(f"the plugin calls itself {manifest.name!r}, not {name!r}")

    existing = store.get(plugin_name)
    if existing and not existing.linked:
        raise StoreError(
            f"{plugin_name} is already installed from {existing.origin} - "
            "remove it first, then link your checkout"
        )

    now = time.time()
    record = store.put(
        Record(
            name=plugin_name,
            source=str(root),
            path=str(root),
            version=manifest.version,
            summary=manifest.summary,
            enabled=True,
            installed=(existing.installed if existing else now),
            updated=now,
        )
    )
    return Installed(record=record, manifest=manifest)


def remove(store: Store, name: str) -> Record:
    """Forget a plugin, and delete its checkout unless it was linked."""
    record = store.require(name)
    if not record.linked:
        store.remove_tree(name)
    store.drop(name)
    return record


def set_enabled(store: Store, name: str, enabled: bool) -> Record:
    return store.set_enabled(name, enabled)


def describe(store: Store, name: str) -> dict[str, str]:
    """Everything pb knows about one installed plugin, for `pb plugin info`."""
    record = store.require(name)
    root = store.root_for(record)
    out = {
        "name": record.name,
        "version": record.version or "-",
        "summary": record.summary or "-",
        "state": "enabled" if record.enabled else "disabled",
        "kind": "linked (your working copy)" if record.linked else "installed from git",
        "source": record.origin or "-",
        "ref": record.ref or ("(default branch)" if not record.linked else "-"),
        "commit": record.commit or "-",
        "path": str(root),
        "exists": "yes" if root.is_dir() else "NO - the directory is gone",
    }
    if not record.linked and (root / ".git").exists():
        out["checked out"] = source.describe(root)
    try:
        manifest = load_manifest(root)
        out["module"] = manifest.import_name
        out["api"] = str(manifest.api)
        if manifest.homepage:
            out["homepage"] = manifest.homepage
    except ManifestError as exc:
        out["manifest"] = f"unreadable - {exc}"
    return out
