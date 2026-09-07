"""A throwaway Ansible repo on disk, for tests that read a repo.

pb's job is to read a real directory layout, so the fixture builds one rather
than mocking `Path`. Nothing here needs an `ansible` binary or a network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pb import meta

SITE_YML = """\
# Everything, in order.
# ====================
---
- import_playbook: base.yml
- import_playbook: web.yml
"""

BASE_YML = """\
# Bring a fresh host up to the baseline.
---
- name: Baseline
  hosts: all
  roles:
    - common
    - { role: hardening, tags: ["security"] }

- name: Baseline, second pass
  hosts: all
  roles:
    - common
"""

WEB_YML = """\
---
- name: Web servers
  hosts: web, staging
  roles:
    - nginx
"""

RESET_YML = """\
# Destructive. Asks first.
---
- name: Reset a host
  hosts: web
  vars_prompt:
    - name: confirm
      prompt: Type the hostname to confirm
  roles:
    - common
"""

BROKEN_YML = """\
# This one does not parse.
---
- name: Unterminated
  hosts: [web
"""

HOSTS_YML = """\
all:
  children:
    web:
      hosts:
        web01:
          ansible_host: 10.0.0.11
        web02:
          ansible_host: 10.0.0.12
    staging:
      hosts:
        stg01:
          ansible_host: 10.0.0.21
"""


@pytest.fixture(autouse=True)
def _no_ambient_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repo.discover reads $ANSIBLE_INVENTORY, so a developer who has it set
    must not get different results from CI."""
    monkeypatch.delenv("ANSIBLE_INVENTORY", raising=False)


@pytest.fixture(autouse=True)
def pb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Everything pb writes outside the repo, redirected into tmp_path.

    `config_dir()` is one directory holding both what the update check
    remembers and which plugins are installed, and `$PB_HOME` moves all of it.
    A test must never read - still less install into, or overwrite a skipped
    version in - the config of whoever is running it. The two off switches go
    with it, so a developer who has either exported does not get different
    results from CI.
    """
    home = tmp_path / "pb-home"
    monkeypatch.setenv("PB_HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("PB_NO_UPDATE_CHECK", raising=False)
    monkeypatch.delenv("PB_NO_PLUGINS", raising=False)
    return home


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """A directory laid out the way pb expects, with no git repo in it."""
    root = tmp_path / "ansible"
    _write(root / "ansible.cfg", "[defaults]\ninventory = inventories/production/hosts.yml\n")

    _write(root / "playbooks" / "site.yml", SITE_YML)
    _write(root / "playbooks" / "base.yml", BASE_YML)
    _write(root / "playbooks" / "web.yml", WEB_YML)
    _write(root / "playbooks" / "reset.yml", RESET_YML)
    _write(root / "playbooks" / "broken.yml", BROKEN_YML)
    # Not a .yml file: pb should not pick it up.
    _write(root / "playbooks" / "notes.md", "# not a playbook\n")

    for role, task_files in (("common", 2), ("hardening", 1), ("nginx", 1)):
        for n in range(task_files):
            name = "main.yml" if n == 0 else f"extra{n}.yml"
            _write(
                root / "roles" / role / "tasks" / name,
                "---\n- name: noop\n  ansible.builtin.debug:\n",
            )
    _write(root / "roles" / "common" / "defaults" / "main.yml", "---\ncommon_user: deploy\n")
    (root / "roles" / "common" / "handlers").mkdir(parents=True, exist_ok=True)
    # A directory under roles/ that is not a role at all.
    (root / "roles" / "empty").mkdir(parents=True, exist_ok=True)

    inv = root / "inventories" / "production"
    _write(inv / "hosts.yml", HOSTS_YML)
    _write(inv / "group_vars" / "all" / "main.yml", "---\ncommon_user: deploy\n")
    _write(
        inv / "group_vars" / "all" / "vault.yml",
        f"{meta.VAULT_HEADER};1.1;AES256\n3132333435363738393061626364656667\n",
    )
    # A vault that was never encrypted - the Vault tab must flag it.
    _write(inv / "group_vars" / "web" / "vault.yml", "---\nvault_web_password: plaintext\n")

    _write(root / ".vault_pass", "hunter2\n")
    return root


@pytest.fixture
def repo(repo_root: Path) -> meta.Repo:
    return meta.Repo.discover(repo_root)


@pytest.fixture
def git_repo(repo_root: Path) -> meta.Repo:
    """The same repo, with one commit and one uncommitted change."""
    if not _have("git"):
        pytest.skip("git not on PATH")
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    }
    run = lambda *argv: subprocess.run(  # noqa: E731
        argv, cwd=repo_root, check=True, capture_output=True, env={**_base_env(), **env}
    )
    run("git", "init", "-q", "-b", "main")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "Initial")
    (repo_root / "playbooks" / "web.yml").write_text(WEB_YML + "\n# edited\n", encoding="utf-8")
    return meta.Repo.discover(repo_root)


def _base_env() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if k != "GIT_DIR"}


def _have(binary: str) -> bool:
    from shutil import which

    return which(binary) is not None


# --- plugins ---------------------------------------------------------
#
# The store lives under `pb_home` above, so every test gets one of its own.


@pytest.fixture
def store(pb_home: Path):
    from pb.plugins.store import Store

    return Store()


# A plugin with one of every hook, written so a test can see each of them fire
# by looking at `pb_probe.EVENTS` in the module it imports.
PROBE_PLUGIN = '''\
"""A plugin that records what pb asked it to do."""

from rich.text import Text
from textual.widgets import DataTable

from pb.plugins import CheckResult, Command, KeySpec, Plugin, TabSpec

EVENTS = []


class Probe(Plugin):
    def tabs(self):
        yield TabSpec(
            id="tab-probe",
            title="Probe",
            factory=lambda: DataTable(id="probe-table"),
            focus="#probe-table",
        )

    def keys(self):
        yield KeySpec(target="playbooks", key="ctrl+b", action="app.probe_shout")
        yield KeySpec(target="app", key="ctrl+j", action="app.probe_shout", show=False)

    def actions(self):
        return {"probe_shout": self.shout, "help": self.instead_of_help}

    def commands(self):
        yield Command(title="Shout", callback=self.shout)

    def shout(self):
        EVENTS.append("shout")

    def instead_of_help(self):
        EVENTS.append("help")
        base = self.base_action("help")
        EVENTS.append("base-help" if base is not None else "no-base")

    def activate(self):
        EVENTS.append("activate")
        self.app.query_one("#probe-table", DataTable).add_columns("Playbook")

    def reloaded(self):
        EVENTS.append("reloaded")
        table = self.app.query_one("#probe-table", DataTable)
        table.clear()
        for playbook in self.playbooks:
            table.add_row(playbook.name)

    def doctor(self):
        yield CheckResult("probe check", True, "fine")

    def before_run(self, request):
        EVENTS.append(f"before:{request.mode}")
        request.argv = [*request.argv, "--probed"]
        request.env["PROBE"] = "1"

    def after_run(self, result):
        EVENTS.append(f"after:{result.exit_code}")

    def detail(self, pane, subject):
        if pane == "playbook":
            return Text("\\nprobe was here\\n")
        return None

    def status_bar(self):
        return Text("  probe")
'''

MANIFEST = """\
[plugin]
name = "{name}"
version = "{version}"
summary = "{summary}"
api = 1
module = "{module}"
"""


@pytest.fixture
def make_plugin(tmp_path: Path):
    """Write a plugin directory and hand back its path."""

    def build(
        name: str = "pb-probe",
        body: str = PROBE_PLUGIN,
        module: str = "",
        version: str = "1.0",
        summary: str = "a test plugin",
        manifest: str | None = None,
        where: Path | None = None,
    ) -> Path:
        module = module or name.replace("-", "_").replace(".", "_")
        root = (where or tmp_path / "plugins") / name
        text = (
            manifest
            if manifest is not None
            else MANIFEST.format(name=name, version=version, summary=summary, module=module)
        )
        _write(root / "pb-plugin.toml", text)
        _write(root / f"{module}.py", body)
        return root

    return build


@pytest.fixture
def linked_plugin(store, make_plugin):
    """A plugin registered in place, the way `pb plugin link` does it."""
    from pb.plugins import manage

    def build(**kwargs) -> Path:
        root = make_plugin(**kwargs)
        manage.link(store, root)
        return root

    return build


@pytest.fixture
def plugin_git_repo(make_plugin):
    """A plugin in a git repository, for the install and update paths.

    A local repository is a git URL like any other, so the install path is
    exercised end to end without a network.
    """
    if not _have("git"):
        pytest.skip("git not on PATH")

    def build(name: str = "pb-probe", **kwargs) -> Path:
        root = make_plugin(name=name, **kwargs)
        _git(root, "init", "-q", "-b", "main")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "Initial")
        return root

    return build


def _git(cwd: Path, *argv: str) -> str:
    env = {
        **_base_env(),
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    }
    done = subprocess.run(
        ["git", *argv], cwd=cwd, check=True, capture_output=True, env=env, text=True
    )
    return done.stdout


@pytest.fixture
def git():
    """Run git in a directory, for tests that need a second commit."""
    if not _have("git"):
        pytest.skip("git not on PATH")
    return _git
