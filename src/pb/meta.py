"""Read-only introspection of the Ansible repo.

Everything the UI knows about playbooks, inventory, roles and vaults is
derived here. Anything that shells out to ansible is slow enough that the
callers run it in a worker thread, never on the UI thread.
"""

from __future__ import annotations

import configparser
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

VAULT_HEADER = "$ANSIBLE_VAULT"

# `ansible-inventory --list` decrypts the vaults, so hostvars come back with
# real secrets in them. Anything whose name looks like a credential is masked
# before it reaches the screen; the Vault tab is the deliberate way to look.
SECRET_KEY_RE = re.compile(
    r"(pass(word|phrase)?|secret|token|api[_-]?key|_key$|^key$|salt|credential"
    r"|private[_-]?key|auth)",
    re.I,
)
MASK = "•••• hidden ••••"


def is_secret(key: str) -> bool:
    return bool(SECRET_KEY_RE.search(key))


def redact(values: dict) -> dict:
    """Copy of `values` with credential-looking entries masked.

    Only strings are masked: `common_disable_ssh_passwords: true` matches the
    name pattern but hiding a boolean helps nobody.
    """
    return {
        k: (MASK if is_secret(k) and isinstance(v, str) and v else v)
        for k, v in values.items()
    }


# --- repo layout -----------------------------------------------------


def find_root(start: Path | None = None) -> Path:
    """Walk up from `start` to the directory holding ansible.cfg."""
    cur = (start or Path.cwd()).resolve()
    for cand in (cur, *cur.parents):
        if (cand / "ansible.cfg").is_file():
            return cand
    return cur


# Where pb looks for an inventory when nothing tells it: these directories
# first, then these files at the repo root.
INVENTORY_DIRS = ("inventories", "inventory")
INVENTORY_FILES = (
    "hosts.yml",
    "hosts.yaml",
    "hosts.ini",
    "hosts",
    "inventory.yml",
    "inventory.yaml",
    "inventory.ini",
)

# An `inventories/` holding several environments is ambiguous. Preferring these
# names keeps pb pointed where it always was for repos laid out that way.
INVENTORY_PREFERRED = ("production", "prod", "main", "default")

# Not environments, even though they are directories under `inventories/`.
INVENTORY_NOT_ENVS = ("group_vars", "host_vars")

# The default of last resort, when the repo has nothing to find. Naming a path
# that does not exist is more useful than naming none: Doctor says so.
INVENTORY_DEFAULT = "inventories/production"


def _find_inventory(root: Path) -> Path | None:
    """Look around the repo for something that looks like an inventory.

    A repo laid out as `inventories/<env>/` gets the environment directory
    rather than its parent, because that is where group_vars lives - and
    merging every environment into one view is never what you meant.
    """
    for name in INVENTORY_DIRS:
        base = root / name
        if not base.is_dir():
            continue
        envs = sorted(
            p for p in base.iterdir() if p.is_dir() and p.name not in INVENTORY_NOT_ENVS
        )
        if not envs:
            # A flat `inventories/` holding hosts.yml and group_vars/.
            return base
        for preferred in INVENTORY_PREFERRED:
            for env in envs:
                if env.name == preferred:
                    return env
        return envs[0]

    for name in INVENTORY_FILES:
        path = root / name
        if path.is_file():
            return path
    return None

# ansible resolves these two itself, so pb must not pass `-i` when the path
# came from one of them - doing so would flatten a multi-source setting down
# to its first entry.
ANSIBLE_KNOWS = ("ansible.cfg", "ANSIBLE_INVENTORY")

# Every origin `Repo.discover` can return, and how Doctor says it. Kept here so
# the two cannot drift apart.
INVENTORY_ORIGINS = {
    "--inventory": "from -i",
    "ANSIBLE_INVENTORY": "from $ANSIBLE_INVENTORY",
    "ansible.cfg": "from ansible.cfg",
    "found": "found in the repo",
    "default": "pb's default - nothing named one",
}


def _first_source(value: str) -> str:
    """ansible accepts a comma-separated list of inventory sources.

    pb shows one inventory and derives group_vars from it, so it works off the
    first. `inventory_args` is what keeps ansible seeing the whole list.
    """
    return next((part.strip() for part in value.split(",") if part.strip()), "")


def _cfg_inventory(root: Path) -> str:
    """The `[defaults] inventory` setting from the repo's ansible.cfg."""
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(root / "ansible.cfg", encoding="utf-8")
    except (OSError, configparser.Error):
        return ""
    return _first_source(parser.get("defaults", "inventory", fallback=""))


@dataclass(frozen=True)
class Repo:
    root: Path
    # An inventory file or directory. Absolute, and not guaranteed to exist.
    inventory: Path
    # How `inventory` was arrived at, for Doctor and for `inventory_args`.
    inventory_origin: str = "default"

    @classmethod
    def discover(cls, root: Path, inventory: str | Path | None = None) -> Repo:
        """Resolve the inventory the way ansible does, then fall back.

        `--inventory`, then $ANSIBLE_INVENTORY, then ansible.cfg - ansible's own
        precedence - then a look around the repo, then the historical default.
        A path that any of the first three name is honoured even if it does not
        exist, because a misconfiguration is worth reporting, not papering over.
        """
        if inventory:
            return cls(root, cls._resolve(root, str(inventory)), "--inventory")

        env = _first_source(os.environ.get("ANSIBLE_INVENTORY", ""))
        if env:
            return cls(root, cls._resolve(root, env), "ANSIBLE_INVENTORY")

        cfg = _cfg_inventory(root)
        if cfg:
            return cls(root, cls._resolve(root, cfg), "ansible.cfg")

        found = _find_inventory(root)
        if found:
            return cls(root, found, "found")

        return cls(root, root / INVENTORY_DEFAULT, "default")

    @staticmethod
    def _resolve(root: Path, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else root / path

    @property
    def playbooks_dir(self) -> Path:
        return self.root / "playbooks"

    @property
    def roles_dir(self) -> Path:
        return self.root / "roles"

    @property
    def group_vars_dir(self) -> Path:
        """group_vars sits beside the inventory source, as ansible expects."""
        base = self.inventory if self.inventory.is_dir() else self.inventory.parent
        return base / "group_vars"

    @property
    def vault_pass_file(self) -> Path:
        return self.root / ".vault_pass"

    @property
    def inventory_args(self) -> list[str]:
        """`-i` for ansible, or nothing when ansible already knows."""
        if self.inventory_origin in ANSIBLE_KNOWS:
            return []
        return ["-i", self.rel(self.inventory)]

    def rel(self, path: Path) -> str:
        """`path` relative to the repo root, or absolute if it lies outside."""
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)


# --- shelling out ----------------------------------------------------


def capture(argv: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    """Run a command, returning (exit code, combined output)."""
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            env={**os.environ, "ANSIBLE_FORCE_COLOR": "0", "ANSIBLE_NOCOLOR": "1"},
        )
    except FileNotFoundError:
        return 127, f"{argv[0]}: not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


# --- playbooks -------------------------------------------------------


@dataclass
class Playbook:
    name: str
    path: Path
    summary: str
    targets: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    interactive: bool = False
    tags: list[str] | None = None  # filled in lazily; None means "not looked up"

    @property
    def kind(self) -> str:
        if self.imports:
            return "aggregate"
        if self.interactive:
            return "interactive"
        return "play"


def _summary_of(text: str, doc: object) -> str:
    """Prefer the file's own header comment; fall back to the first play name."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line in ("---", ""):
            if lines:
                break
            continue
        if line.startswith("#"):
            body = line.lstrip("#").strip()
            # Skip the ==== rules used as section dividers in this repo.
            if body and set(body) != {"="}:
                lines.append(body)
            continue
        break
    if lines:
        return " ".join(lines)
    if isinstance(doc, list) and doc and isinstance(doc[0], dict):
        return str(doc[0].get("name") or doc[0].get("import_playbook") or "")
    return ""


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def discover_playbooks(repo: Repo) -> list[Playbook]:
    found: list[Playbook] = []
    for path in sorted(repo.playbooks_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError:
            doc = None

        pb = Playbook(
            name=path.stem,
            path=path,
            summary=_summary_of(text, doc),
        )
        if isinstance(doc, list):
            for play in doc:
                if not isinstance(play, dict):
                    continue
                if "import_playbook" in play:
                    pb.imports.append(str(play["import_playbook"]).removesuffix(".yml"))
                    continue
                # Several plays may target the same group; name it once.
                for target in _as_list(play.get("hosts")):
                    if target not in pb.targets:
                        pb.targets.append(target)
                if play.get("vars_prompt"):
                    pb.interactive = True
                for role in play.get("roles") or []:
                    name = role.get("role") if isinstance(role, dict) else role
                    if name:
                        pb.roles.append(str(name))
        found.append(pb)

    # site.yml first, then aggregates, then the rest alphabetically.
    def order(p: Playbook) -> tuple[int, str]:
        return (0 if p.name == "site" else 1 if p.imports else 2, p.name)

    return sorted(found, key=order)


TAGS_RE = re.compile(r"TASK TAGS:\s*\[(.*?)\]", re.S)


def playbook_tags(repo: Repo, playbook: Playbook) -> list[str]:
    """Ask ansible for the real tag list, including ones roles add."""
    code, out = capture(
        ["ansible-playbook", repo.rel(playbook.path), "--list-tags", *repo.inventory_args],
        repo.root,
    )
    if code != 0:
        return []
    tags: set[str] = set()
    for match in TAGS_RE.findall(out):
        for tag in match.split(","):
            tag = tag.strip()
            if tag and tag != "never":
                tags.add(tag)
    return sorted(tags)


HOSTS_HEADER_RE = re.compile(r"^\s*hosts \((\d+)\):\s*$")


def playbook_hosts(repo: Repo, playbook: Playbook, limit: str = "") -> list[str]:
    """The hosts a run would actually touch, straight from ansible.

    The Targets column shows patterns; this resolves them. For an aggregate
    playbook the patterns are meaningless on their own, so this is the only
    honest answer to "what am I about to change".
    """
    argv = ["ansible-playbook", repo.rel(playbook.path), "--list-hosts", *repo.inventory_args]
    if limit:
        argv += ["--limit", limit]
    code, out = capture(argv, repo.root)
    if code != 0:
        return []

    hosts: list[str] = []
    collecting = False
    for raw in out.splitlines():
        if HOSTS_HEADER_RE.match(raw):
            collecting = True
            continue
        if not collecting:
            continue
        line = raw.strip()
        # The host block ends at the blank line before the next play.
        if not line:
            collecting = False
            continue
        if line.startswith(("play #", "pattern:", "playbook:")):
            collecting = False
            continue
        if line not in hosts:
            hosts.append(line)
    return hosts


# --- inventory -------------------------------------------------------


@dataclass
class Host:
    name: str
    address: str
    groups: list[str]
    vars: dict


@dataclass
class Inventory:
    hosts: list[Host] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=dict)
    error: str = ""
    # What ansible said around the JSON. Usually empty; when it is not, it is
    # the reason the inventory looks emptier than you expected.
    warning: str = ""


def _json_payload(out: str) -> tuple[object, str]:
    """The first JSON value in `out`, and whatever ansible printed around it.

    `capture` merges stderr into stdout and `ansible-inventory` writes its
    [WARNING] lines there, so the JSON is usually not the whole output. Taking
    the whole thing as JSON turns "your inventory did not parse" into "pb could
    not parse ansible's output", which tells you nothing.
    """
    start = out.find("{")
    if start < 0:
        return None, out.strip()
    try:
        data, end = json.JSONDecoder().raw_decode(out[start:])
    except json.JSONDecodeError:
        return None, out.strip()
    return data, (out[:start] + out[start + end :]).strip()


def load_inventory(repo: Repo) -> Inventory:
    code, out = capture(["ansible-inventory", "--list", *repo.inventory_args], repo.root)
    if code != 0:
        return Inventory(error=out.strip() or f"ansible-inventory exited {code}")

    data, noise = _json_payload(out)
    if not isinstance(data, dict):
        return Inventory(error=noise or "ansible-inventory printed no inventory")

    hostvars = data.get("_meta", {}).get("hostvars", {})
    groups: dict[str, list[str]] = {}
    membership: dict[str, list[str]] = {}
    for group, body in data.items():
        if group in ("_meta", "all") or not isinstance(body, dict):
            continue
        members = list(body.get("hosts") or [])
        if not members:
            continue
        groups[group] = sorted(members)
        for host in members:
            membership.setdefault(host, []).append(group)

    hosts = [
        Host(
            name=name,
            address=str(hostvars.get(name, {}).get("ansible_host", "")),
            groups=sorted(membership.get(name, [])),
            vars=hostvars.get(name, {}),
        )
        for name in sorted(hostvars)
    ]
    return Inventory(hosts=hosts, groups=dict(sorted(groups.items())), warning=noise)


# --- roles -----------------------------------------------------------


@dataclass
class Role:
    name: str
    path: Path
    tasks: int
    parts: list[str]
    used_by: list[str]


def discover_roles(repo: Repo, playbooks: list[Playbook]) -> list[Role]:
    users: dict[str, list[str]] = {}
    for pb in playbooks:
        # A playbook may use the same role in several plays; name it once.
        for role in dict.fromkeys(pb.roles):
            users.setdefault(role, []).append(pb.name)

    roles: list[Role] = []
    for path in sorted(p for p in repo.roles_dir.glob("*") if p.is_dir()):
        task_files = sorted(path.glob("tasks/*.yml"))
        parts = [
            part
            for part in ("defaults", "handlers", "templates", "files", "vars", "meta")
            if (path / part).is_dir()
        ]
        roles.append(
            Role(
                name=path.name,
                path=path,
                tasks=len(task_files),
                parts=parts,
                used_by=sorted(users.get(path.name, [])),
            )
        )
    return roles


# --- vaults ----------------------------------------------------------


@dataclass
class Vault:
    group: str
    path: Path
    encrypted: bool
    size: int


def discover_vaults(repo: Repo) -> list[Vault]:
    vaults: list[Vault] = []
    for path in sorted(repo.group_vars_dir.glob("*/vault.yml")):
        head = ""
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                head = handle.readline()
        except OSError:
            pass
        vaults.append(
            Vault(
                group=path.parent.name,
                path=path,
                encrypted=head.startswith(VAULT_HEADER),
                size=path.stat().st_size if path.exists() else 0,
            )
        )
    return vaults


# --- git -------------------------------------------------------------


def changed_paths(repo: Repo) -> set[str]:
    """Repo-relative paths that differ from HEAD, staged or not."""
    code, out = capture(["git", "status", "--porcelain"], repo.root, timeout=10)
    if code != 0:
        return set()
    paths: set[str] = set()
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        # Renames read "old -> new"; the new name is what exists now.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path.strip('"'))
    return paths


def git_diff(repo: Repo, max_lines: int = 4000) -> str:
    """`git status` plus the working-tree diff, for the changes viewer."""
    _, status = capture(["git", "status", "--short", "--branch"], repo.root, timeout=10)
    _, diff = capture(["git", "diff", "HEAD"], repo.root, timeout=30)
    lines = diff.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines] + ["", f"… {len(diff.splitlines()) - max_lines} more lines"]
    return status.rstrip() + "\n\n" + "\n".join(lines)


def git_status(repo: Repo) -> tuple[str, int]:
    """Return (branch, number of changed files). Empty branch if not a repo."""
    code, out = capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo.root, timeout=10)
    if code != 0:
        return "", 0
    branch = out.strip()
    code, out = capture(["git", "status", "--porcelain"], repo.root, timeout=10)
    dirty = len([ln for ln in out.splitlines() if ln.strip()]) if code == 0 else 0
    return branch, dirty
