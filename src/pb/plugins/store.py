"""Where installed plugins live, and the record of what is installed.

One directory per plugin under the pb config directory, plus a JSON state file
naming where each came from and which commit is checked out. The state file is
the source of truth: a directory pb has no record of is ignored, so a failed
install cannot come back to life on the next start.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..config import config_dir as _config_dir

STATE_VERSION = 1
STATE_NAME = "plugins.json"


class StoreError(Exception):
    """The store cannot do what was asked - usually a name that is not installed."""


# Re-exported so a plugin need not know which module the rule lives in.
config_dir = _config_dir


@dataclass
class Record:
    """One installed plugin, as the state file remembers it."""

    name: str
    # What the user typed, kept verbatim so `update` and `pb plugin list` can
    # show where this came from.
    source: str = ""
    # The git URL that `source` resolved to. Empty for a linked checkout.
    url: str = ""
    ref: str = ""
    commit: str = ""
    version: str = ""
    summary: str = ""
    enabled: bool = True
    installed: float = field(default_factory=time.time)
    updated: float = 0.0
    # Set for `pb plugin link`: a working copy pb reads in place and never
    # touches with git. This is the development loop.
    path: str = ""

    @property
    def linked(self) -> bool:
        return bool(self.path)

    @property
    def origin(self) -> str:
        return self.path if self.linked else (self.source or self.url)

    @property
    def short_commit(self) -> str:
        return self.commit[:7]


class Store:
    """The plugin directory and its state file."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or config_dir()
        self.plugins_dir = self.root / "plugins"
        self.state_file = self.root / STATE_NAME
        self.data_root = self.root / "state"

    # --- state ---------------------------------------------------------

    def records(self) -> list[Record]:
        """Every installed plugin, in install order. Never raises."""
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(data, dict):
            return []
        out: list[Record] = []
        for entry in data.get("plugins", []):
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            known = {k: v for k, v in entry.items() if k in Record.__dataclass_fields__}
            try:
                out.append(Record(**known))
            except TypeError:
                continue
        return out

    def get(self, name: str) -> Record | None:
        return next((r for r in self.records() if r.name == name), None)

    def require(self, name: str) -> Record:
        record = self.get(name)
        if record is None:
            raise StoreError(f"{name} is not installed")
        return record

    def save(self, records: list[Record]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"version": STATE_VERSION, "plugins": [asdict(r) for r in records]}
        # Write beside the target and rename, so an interrupted save cannot
        # leave pb with a truncated list of what is installed.
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.state_file)

    def put(self, record: Record) -> Record:
        """Insert or replace one record, keeping the existing order."""
        records = self.records()
        for i, existing in enumerate(records):
            if existing.name == record.name:
                records[i] = record
                break
        else:
            records.append(record)
        self.save(records)
        return record

    def drop(self, name: str) -> None:
        self.save([r for r in self.records() if r.name != name])

    def set_enabled(self, name: str, enabled: bool) -> Record:
        record = self.require(name)
        record.enabled = enabled
        return self.put(record)

    # --- directories ----------------------------------------------------

    def dir_for(self, name: str) -> Path:
        """Where a git-installed plugin's checkout lives."""
        return self.plugins_dir / name

    def root_for(self, record: Record) -> Path:
        """The directory to read a plugin from - the link target, if linked."""
        return Path(record.path).expanduser() if record.linked else self.dir_for(record.name)

    def data_dir_for(self, name: str) -> Path:
        """A private directory a plugin may keep its own state in."""
        return self.data_root / name

    def remove_tree(self, name: str) -> None:
        """Delete a plugin's checkout. Refuses anything outside the store."""
        target = self.dir_for(name).resolve()
        base = self.plugins_dir.resolve()
        if target == base or base not in target.parents:
            raise StoreError(f"refusing to delete {target}: outside {base}")
        shutil.rmtree(target, ignore_errors=True)
