"""pb's plugin system.

A plugin is a git repository with a `pb-plugin.toml` and an importable module
that defines a `Plugin` subclass. pb clones it, imports it at start-up, and
lets it add tabs, keys and Doctor checks, react to runs, or replace an action
the base app already has.

Plugins import from here:

    from pb.plugins import CheckResult, KeySpec, Plugin, TabSpec

The authoring guide is `docs/PLUGINS.md`; `pb plugin new` writes a working
plugin to start from.
"""

from __future__ import annotations

from .api import (
    API_VERSION,
    PANES,
    CheckResult,
    Command,
    KeySpec,
    Plugin,
    RunRequest,
    RunResult,
    TabSpec,
)
from .loader import Failure, Loaded, load_all
from .manifest import MANIFEST_NAME, Manifest, ManifestError
from .store import Record, Store, StoreError, config_dir

__all__ = [
    "API_VERSION",
    "MANIFEST_NAME",
    "PANES",
    "CheckResult",
    "Command",
    "Failure",
    "KeySpec",
    "Loaded",
    "Manifest",
    "ManifestError",
    "Plugin",
    "Record",
    "RunRequest",
    "RunResult",
    "Store",
    "StoreError",
    "TabSpec",
    "config_dir",
    "load_all",
]
