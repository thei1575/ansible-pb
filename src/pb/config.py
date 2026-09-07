"""Where pb keeps what belongs to the machine rather than to the repo.

Two things live outside the Ansible repo: what the update check remembers, and
which plugins are installed. Neither is about the repo pb happens to be
pointed at, and both belong in the same place — so the rule for finding that
place lives here rather than being spelled out twice and drifting.
"""

from __future__ import annotations

import os
from pathlib import Path


def config_dir() -> Path:
    """pb's config directory: $PB_HOME, else $XDG_CONFIG_HOME/pb, else ~/.config/pb.

    `$PB_HOME` moves the whole directory — everything pb writes outside the
    repo — which is what makes pb testable and what lets someone keep it
    somewhere other than under `~/.config`.
    """
    home = os.environ.get("PB_HOME")
    if home:
        return Path(home).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "pb"
