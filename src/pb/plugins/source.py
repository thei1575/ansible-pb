"""Getting a plugin from GitHub - or from anything else git can clone.

pb shells out to `git`, the way it shells out to ansible: no bundled HTTP
client, no tarball unpacking, and `git` already knows about the user's SSH
keys, credential helper and proxy. A plugin's checkout is a normal clone, so
`git log` in it tells the truth about what is installed.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

GITHUB = "https://github.com/{owner}/{repo}.git"

# `owner/repo`, optionally `@ref`, optionally prefixed `gh:` or `github.com/`.
SHORTHAND_RE = re.compile(
    r"^(?:gh:|github:|(?:https?://)?github\.com/)?"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)/"
    r"(?P<repo>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])??)(?:\.git)?"
    r"(?:@(?P<ref>[^\s@]+))?$"
)

URL_SCHEMES = ("https://", "http://", "ssh://", "git://", "file://")

DEFAULT_TIMEOUT = 300


class SourceError(Exception):
    """git could not do it, or the spec is not something pb can fetch."""


@dataclass(frozen=True)
class Source:
    """Where a plugin comes from, resolved."""

    url: str
    ref: str = ""
    # What the plugin would be called if the manifest did not say - the last
    # path segment. Only ever a fallback: the manifest wins.
    name_hint: str = ""
    # What the user typed, kept for `pb plugin list`.
    spec: str = ""


def resolve(spec: str, ref: str = "") -> Source:
    """Turn what the user typed into a git URL and a ref.

    `owner/repo` means GitHub, because that is where pb plugins are published.
    Anything with a scheme, an `scp`-style `git@host:path`, or a path to a
    local repository is passed to git untouched, so a private mirror or a
    checkout on disk works without pb needing to know about it.
    """
    spec = spec.strip()
    if not spec:
        raise SourceError("no plugin source given")

    if spec.startswith(URL_SCHEMES) or _is_scp_style(spec):
        url, _, fragment = spec.partition("#")
        return Source(url=url, ref=ref or fragment, name_hint=_name_from_url(url), spec=spec)

    local = _local_repo(spec)
    if local is not None:
        return Source(url=str(local), ref=ref, name_hint=local.name, spec=spec)

    match = SHORTHAND_RE.match(spec)
    if match:
        owner, repo = match["owner"], match["repo"]
        return Source(
            url=GITHUB.format(owner=owner, repo=repo),
            ref=ref or (match["ref"] or ""),
            name_hint=repo.removesuffix(".git"),
            spec=spec,
        )

    raise SourceError(
        f"{spec!r} is not a plugin source. Use owner/repo for GitHub, a git URL, "
        "or a path to a local checkout."
    )


def _is_scp_style(spec: str) -> bool:
    """`git@github.com:owner/repo.git` - a URL to git, but not to urllib."""
    head, sep, tail = spec.partition(":")
    return bool(sep) and "@" in head and "/" not in head and not tail.startswith("//")


def _local_repo(spec: str) -> Path | None:
    """A directory on disk that git can clone from."""
    if not (spec.startswith((".", "/", "~")) or Path(spec).exists()):
        return None
    path = Path(spec).expanduser()
    if not path.is_dir():
        return None
    if not ((path / ".git").exists() or (path / "HEAD").is_file()):
        raise SourceError(f"{path} exists but is not a git repository")
    return path.resolve()


def _name_from_url(url: str) -> str:
    tail = url.rstrip("/").rpartition("/")[2] or url.rpartition(":")[2]
    return tail.removesuffix(".git")


# --- git ----------------------------------------------------------------


def have_git() -> bool:
    from shutil import which

    return which("git") is not None


def _git(argv: list[str], cwd: Path | None = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Run git, returning stdout. Raises SourceError with git's own message."""
    try:
        proc = subprocess.run(
            ["git", *argv],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            env={
                **os.environ,
                # Never stop for a password prompt: a hung install with no
                # terminal to type into is worse than a clean failure.
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "",
                "GCM_INTERACTIVE": "never",
            },
        )
    except FileNotFoundError as exc:
        raise SourceError("git is not on PATH - pb installs plugins with git") from exc
    except subprocess.TimeoutExpired as exc:
        raise SourceError(f"git {argv[0]} timed out after {timeout}s") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).decode("utf-8", "replace").strip()
        raise SourceError(detail.splitlines()[-1] if detail else f"git {argv[0]} failed")
    return proc.stdout.decode("utf-8", "replace")


def clone(source: Source, dest: Path, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Clone `source` into `dest` and return the commit that landed there.

    A ref is checked out detached, so an install pinned to a tag stays pinned:
    `update` on a pinned plugin re-resolves the same ref rather than drifting
    onto a branch.
    """
    if dest.exists():
        raise SourceError(f"{dest} already exists")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(["clone", "--quiet", "--no-tags", source.url, str(dest)], timeout=timeout)
    if source.ref:
        try:
            _checkout(dest, source.ref, timeout=timeout)
        except SourceError:
            # Clean up rather than leave a checkout on the wrong commit.
            import shutil

            shutil.rmtree(dest, ignore_errors=True)
            raise
    return head(dest)


def _checkout(repo: Path, ref: str, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Check out a tag, a branch, or a commit, whichever the ref turns out to be."""
    fetched = False
    try:
        _git(["fetch", "--quiet", "--tags", "origin", ref], cwd=repo, timeout=timeout)
        fetched = True
    except SourceError:
        # A remote may refuse to fetch a ref by name - an unadvertised commit,
        # typically - and yet already have it in the clone. Try anyway.
        pass

    candidates = (["FETCH_HEAD"] if fetched else []) + [ref, f"origin/{ref}"]
    failures: list[str] = []
    for candidate in candidates:
        try:
            _git(["checkout", "--quiet", "--detach", candidate], cwd=repo, timeout=timeout)
            return
        except SourceError as exc:
            failures.append(str(exc))
    raise SourceError(f"no such ref {ref!r} in this repository - {failures[-1]}")


def update(repo: Path, ref: str = "", timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str]:
    """Fetch and move the checkout on. Returns (old commit, new commit).

    pb owns this directory, so an update discards local edits in it - develop
    against a checkout of your own with `pb plugin link` instead.
    """
    if not (repo / ".git").exists():
        raise SourceError(f"{repo} is not a git checkout - reinstall the plugin")
    before = head(repo)
    if ref:
        _checkout(repo, ref, timeout=timeout)
    else:
        _git(["fetch", "--quiet", "--tags", "origin"], cwd=repo, timeout=timeout)
        _git(["reset", "--quiet", "--hard", f"origin/{default_branch(repo)}"], cwd=repo)
    return before, head(repo)


def head(repo: Path) -> str:
    return _git(["rev-parse", "HEAD"], cwd=repo, timeout=30).strip()


def default_branch(repo: Path) -> str:
    """The remote's own default branch, falling back to the current one."""
    try:
        ref = _git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=repo, timeout=30).strip()
        return ref.rpartition("/")[2]
    except SourceError:
        pass
    try:
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, timeout=30).strip()
    except SourceError:
        branch = ""
    return branch if branch and branch != "HEAD" else "main"


def describe(repo: Path) -> str:
    """A human-readable "what is checked out here", for `pb plugin info`."""
    try:
        return _git(
            ["log", "-1", "--format=%h %ad %s", "--date=short"], cwd=repo, timeout=30
        ).strip()
    except SourceError as exc:
        return str(exc)


def remote_url(repo: Path) -> str:
    try:
        return _git(["remote", "get-url", "origin"], cwd=repo, timeout=30).strip()
    except SourceError:
        return ""
