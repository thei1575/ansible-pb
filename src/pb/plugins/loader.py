"""Turning installed directories into live Plugin objects.

Importing third-party code is the one place pb has to be paranoid: a plugin
that raises on import, declares nothing, or was written for a different API
must cost the user a row on the Plugins tab, not a traceback instead of their
console. Nothing here raises - failures come back as `Failure` records.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from .api import API_VERSION, Plugin
from .manifest import Manifest, ManifestError, css_paths
from .manifest import load as load_manifest
from .store import Record, Store

# A module may name what pb should instantiate. Without it, pb takes the
# Plugin subclasses the module itself defines.
ENTRY_POINT = "PB_PLUGIN"


@dataclass
class Failure:
    """A plugin that could not be loaded, and why."""

    name: str
    message: str
    detail: str = ""
    # Where it went wrong: "manifest", "import", "entry-point", "construct".
    stage: str = "import"

    def __str__(self) -> str:
        return f"{self.name}: {self.message}"


@dataclass
class Loaded:
    """The result of a load pass: what came up, and what did not."""

    plugins: list[Plugin] = field(default_factory=list)
    manifests: dict[str, Manifest] = field(default_factory=dict)
    records: dict[str, Record] = field(default_factory=dict)
    failures: list[Failure] = field(default_factory=list)
    css: list[Path] = field(default_factory=list)

    def by_name(self, name: str) -> Plugin | None:
        return next((p for p in self.plugins if p.name == name), None)


def load_all(store: Store) -> Loaded:
    """Import every enabled plugin the store knows about, in install order."""
    loaded = Loaded()
    for record in store.records():
        loaded.records[record.name] = record
        if not record.enabled:
            continue
        _load_one(store, record, loaded)
    return loaded


def _load_one(store: Store, record: Record, loaded: Loaded) -> None:
    root = store.root_for(record)
    if not root.is_dir():
        loaded.failures.append(
            Failure(
                record.name,
                f"{root} is missing" + (" - the linked directory moved?" if record.linked else ""),
                stage="manifest",
            )
        )
        return

    try:
        manifest = load_manifest(root)
    except ManifestError as exc:
        loaded.failures.append(Failure(record.name, str(exc), stage="manifest"))
        return

    if manifest.name != record.name:
        loaded.failures.append(
            Failure(
                record.name,
                f"the manifest in {root} now calls itself {manifest.name!r}"
                " - reinstall it under that name",
                stage="manifest",
            )
        )
        return

    clash = next(
        (
            other
            for other, seen in loaded.manifests.items()
            if seen.import_name == manifest.import_name
        ),
        None,
    )
    if clash is not None:
        loaded.failures.append(
            Failure(
                record.name,
                f"imports {manifest.import_name!r}, which {clash} already uses"
                " - one of them has to rename its module",
                stage="import",
            )
        )
        return

    loaded.manifests[record.name] = manifest

    try:
        module = _import(root, manifest)
    except Exception as exc:  # plugin code: anything at all can come out
        loaded.failures.append(
            Failure(
                record.name,
                f"{type(exc).__name__}: {exc}",
                detail=traceback.format_exc(),
                stage="import",
            )
        )
        return

    classes = _entry_points(module)
    if not classes:
        loaded.failures.append(
            Failure(
                record.name,
                f"{manifest.import_name} defines no Plugin subclass and no {ENTRY_POINT}",
                stage="entry-point",
            )
        )
        return

    for cls in classes:
        try:
            plugin = cls() if isinstance(cls, type) else cls
        except Exception as exc:
            loaded.failures.append(
                Failure(
                    record.name,
                    f"{getattr(cls, '__name__', cls)}() raised {type(exc).__name__}: {exc}",
                    detail=traceback.format_exc(),
                    stage="construct",
                )
            )
            continue
        plugin.name = record.name
        plugin.version = manifest.version or record.version
        plugin.summary = manifest.summary or record.summary
        plugin.root = root
        plugin.data_dir = store.data_dir_for(record.name)
        loaded.plugins.append(plugin)

    loaded.css.extend(css_paths(root, manifest))


def _import(root: Path, manifest: Manifest):
    """Import the plugin's module with its own directories on sys.path.

    The entries go in front, but pb's own package is imported by now, so a
    plugin cannot shadow `pb` itself.
    """
    for entry in manifest.python_path:
        path = str((root / entry).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)

    # Drop any cached copy - of this plugin from an earlier pass, or of
    # something else that had the name - and import from disk. `reload` will
    # not do: it merges into the old module dict, so a class a rewritten file
    # has deleted stays visible and gets loaded a second time.
    name = manifest.import_name
    for key in [name, *[k for k in sys.modules if k.startswith(f"{name}.")]]:
        sys.modules.pop(key, None)
    importlib.invalidate_caches()
    return importlib.import_module(name)


def _entry_points(module) -> list[type[Plugin] | Plugin]:
    """What in this module is a plugin.

    `PB_PLUGIN` wins if the module sets it - a class, an instance, or a list
    of either. Otherwise every Plugin subclass the module defines itself,
    which is the common case and needs no boilerplate.
    """
    declared = getattr(module, ENTRY_POINT, None)
    if declared is not None:
        items = declared if isinstance(declared, (list, tuple)) else [declared]
        return [i for i in items if isinstance(i, Plugin) or _is_plugin_class(i)]

    return [
        obj
        for obj in vars(module).values()
        if _is_plugin_class(obj) and obj.__module__ == module.__name__
    ]


def _is_plugin_class(obj: object) -> bool:
    return inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin


def check(store: Store) -> list[Failure]:
    """Load everything and report only the problems - `pb plugin doctor`."""
    return load_all(store).failures


def api_version() -> int:
    return API_VERSION
