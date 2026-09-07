"""Check GitHub for a newer pb, and install it if you say yes.

pb is installed from git rather than PyPI, so the check reads the repository's
releases over the GitHub API, falling back to its tags for a version that was
tagged but never released. The release notes come from the release body, or
failing that from the CHANGELOG entries between the version you have and the
one on offer - so what the prompt shows is what you would be getting.

This is the only network connection pb makes on its own: one unauthenticated
GET to api.github.com, at most once a day, sending nothing but a
`pb/<version>` User-Agent. `--no-update-check` or `PB_NO_UPDATE_CHECK=1` turns
it off.

Nothing here installs anything by itself. `upgrade_command` builds the command
and the caller shows it before running it, the same as every other command pb
runs.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import __version__
from .config import config_dir

REPO = "thei1575/ansible-pb"
GIT_URL = f"git+https://github.com/{REPO}"
API = f"https://api.github.com/repos/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}"

CHECK_EVERY = 24 * 3600  # seconds between automatic checks
TIMEOUT = 6.0            # a startup check must not hold anything up
MAX_BYTES = 1 << 20      # a release body is a few KB; refuse to read a flood


# --- versions --------------------------------------------------------

_VERSION_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(.*)$")


def parse_version(text: str) -> tuple[int, int, int, int, str] | None:
    """`v0.2.0` -> a comparable tuple, or None if that is not a version.

    A suffix (`0.2.0rc1`, `0.2.0-beta`) sorts below the plain release, which
    is what a pre-release is. pb tags plain `vX.Y.Z`, so a suffix only has to
    be ordered sensibly, not understood.
    """
    match = _VERSION_RE.match(text.strip())
    if not match:
        return None
    major, minor, patch, suffix = match.groups()
    suffix = suffix.strip()
    return int(major), int(minor or 0), int(patch or 0), 0 if suffix else 1, suffix


def is_newer(candidate: str, current: str) -> bool:
    """True when `candidate` is a version and it is above `current`."""
    new, old = parse_version(candidate), parse_version(current)
    return bool(new and old and new > old)


# --- what GitHub says ------------------------------------------------


@dataclass(frozen=True)
class Release:
    version: str          # `0.2.0`, as it would print from `pb --version`
    tag: str              # `v0.2.0`, as the installer has to be given it
    notes: str = ""       # release body, or the CHANGELOG entries since
    url: str = ""         # where to read it in a browser


def _get(url: str, timeout: float, accept: str) -> str | None:
    """One GET. Returns None for anything that goes wrong - offline included."""
    request = urllib.request.Request(  # noqa: S310 - the URL is a constant above
        url,
        headers={
            "Accept": accept,
            "User-Agent": f"pb/{__version__}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read(MAX_BYTES).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _json(body: str | None) -> object:
    if not body:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def latest_release(timeout: float = TIMEOUT) -> Release | None:
    """The newest published release, or the newest tag if there is no release.

    `releases/latest` already excludes drafts and pre-releases, so a version
    that is not meant for people never reaches the prompt.
    """
    data = _json(_get(f"{API}/releases/latest", timeout, "application/vnd.github+json"))
    if isinstance(data, dict) and data.get("tag_name"):
        tag = str(data["tag_name"])
        return Release(
            version=tag.lstrip("v"),
            tag=tag,
            notes=str(data.get("body") or "").strip(),
            url=str(data.get("html_url") or ""),
        )
    return _latest_tag(timeout)


def _latest_tag(timeout: float) -> Release | None:
    """A repo can be tagged without a release ever being published for it."""
    data = _json(_get(f"{API}/tags?per_page=100", timeout, "application/vnd.github+json"))
    if not isinstance(data, list):
        return None
    best: tuple | None = None
    tag = ""
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        version = parse_version(name)
        if version and (best is None or version > best):
            best, tag = version, name
    if not tag:
        return None
    return Release(
        version=tag.lstrip("v"),
        tag=tag,
        url=f"https://github.com/{REPO}/releases/tag/{tag}",
    )


# --- release notes ---------------------------------------------------

# Keep a Changelog: one `## [x.y.z] - date` heading per release, newest first.
_HEADING_RE = re.compile(r"^##\s+\[?v?([^\]\s]+)\]?")


def changelog_since(text: str, current: str) -> str:
    """The CHANGELOG sections for every version above `current`.

    A heading that is not a version - `## [Unreleased]` above all of them - is
    left out along with its body: it is not what you would be getting.
    """
    kept: list[str] = []
    keeping = False
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            keeping = is_newer(match.group(1), current)
            if keeping:
                kept.append(line.rstrip())
            continue
        if keeping:
            kept.append(line.rstrip())
    return "\n".join(kept).strip()


def release_notes(release: Release, current: str, timeout: float = TIMEOUT) -> str:
    """The CHANGELOG entries between `current` and `release`, read from the tag.

    Falls back to `main` for a tag pushed before the changelog was written on
    it, which is the ordering a release from a branch tends to produce.
    """
    for ref in (release.tag, "main"):
        notes = changelog_since(_get(f"{RAW}/{ref}/CHANGELOG.md", timeout, "text/plain") or "",
                                current)
        if notes:
            return notes
    return ""


# --- what pb remembers between runs ----------------------------------


def state_path() -> Path:
    """`~/.config/pb/update.json`, wherever `config_dir()` puts that.

    Deliberately outside the Ansible repo: which version you skipped is about
    your machine, not about the repo you happen to be pointing pb at.
    """
    return config_dir() / "update.json"


def load_state() -> dict:
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(state: dict) -> None:
    """Never raises: failing to remember a skip must not take the app down."""
    path = state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass


def skip(version: str) -> None:
    """Remember that this version was declined. Nothing offers it again."""
    save_state({**load_state(), "skipped": version})


def forget_skip() -> None:
    save_state({k: v for k, v in load_state().items() if k != "skipped"})


def due(state: dict, now: float, every: float = CHECK_EVERY) -> bool:
    last = state.get("last_check")
    if not isinstance(last, int | float) or isinstance(last, bool):
        return True
    # A clock that moved backwards must not park the next check in the future.
    return not (0 <= now - last < every)


def disabled() -> bool:
    return os.environ.get("PB_NO_UPDATE_CHECK", "").strip().lower() not in ("", "0", "false", "no")


# --- the check -------------------------------------------------------


@dataclass(frozen=True)
class Result:
    release: Release | None = None  # set only when there is something newer
    checked: bool = False           # False when the check was off or not due
    error: str = ""


def check(
    current: str,
    *,
    force: bool = False,
    now: float | None = None,
    timeout: float = TIMEOUT,
) -> Result:
    """Look for a newer pb. Blocks on the network - call it from a thread.

    `force` is the user asking for it there and then: it ignores the once-a-day
    interval, a version they skipped, and the opt-out, which only ever meant
    "do not go looking on your own".
    """
    now = time.time() if now is None else now
    state = load_state()
    if not force and (disabled() or not due(state, now)):
        return Result()

    release = latest_release(timeout)
    save_state({**state, "last_check": now})
    if release is None:
        return Result(checked=True, error=f"could not reach github.com/{REPO}")
    if not is_newer(release.version, current):
        return Result(checked=True)
    if not force and state.get("skipped") == release.version:
        return Result(checked=True)
    if not release.notes:
        release = replace(release, notes=release_notes(release, current, timeout))
    return Result(checked=True, release=release)


# --- installing it ---------------------------------------------------

INSTALL_LABELS = {
    "uv": "uv tool",
    "pipx": "pipx",
    "pip": "pip",
    "source": "a source checkout",
}


@dataclass(frozen=True)
class Upgrade:
    how: str                                       # the installer, as you know it
    argv: list[str] = field(default_factory=list)  # empty: pb will not do it itself
    manual: str = ""                               # what to do by hand instead

    @property
    def possible(self) -> bool:
        return bool(self.argv)


def install_method(prefix: Path | None = None, package: Path | None = None) -> str:
    """Which installer pb was installed with, read off where it lives."""
    parts = (prefix or Path(sys.prefix)).parts
    for first, second in zip(parts, parts[1:], strict=False):
        if (first, second) == ("uv", "tools"):
            return "uv"
        if (first, second) == ("pipx", "venvs"):
            return "pipx"
    # An editable install, or `uv run` from a clone, leaves pb outside
    # site-packages: there the checkout is the install, and git moves it.
    pkg = package or Path(__file__).resolve().parent
    if "site-packages" not in pkg.parts:
        return "source"
    return "pip"


def install_label(method: str | None = None) -> str:
    """How to say the installer pb came from, for Doctor."""
    return INSTALL_LABELS[method or install_method()]


def upgrade_command(tag: str, method: str | None = None) -> Upgrade:
    """The command that installs `tag`, for the installer pb came from.

    It pins the tag rather than upgrading loosely because pb is installed from
    a git URL: `uv tool upgrade` on one of those keeps the ref it was installed
    with, so it would report success and change nothing.
    """
    method = method or install_method()
    target = f"{GIT_URL}@{tag}"
    label = INSTALL_LABELS[method]
    if method == "uv":
        return Upgrade(label, ["uv", "tool", "install", "--force", target])
    if method == "pipx":
        return Upgrade(label, ["pipx", "install", "--force", target])
    if method == "pip":
        return Upgrade(label, [sys.executable, "-m", "pip", "install", "--upgrade", target])
    checkout = Path(__file__).resolve().parents[2]
    return Upgrade(
        label,
        manual=f"pb runs from {checkout} - `git pull` there, or `git checkout {tag}`.",
    )
