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
    # A vault that was never encrypted — the Vault tab must flag it.
    _write(inv / "group_vars" / "web" / "vault.yml", "---\nvault_web_password: plaintext\n")

    _write(root / ".vault_pass", "hunter2\n")
    return root


@pytest.fixture
def repo(repo_root: Path) -> meta.Repo:
    return meta.Repo(root=repo_root)


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
    return meta.Repo(root=repo_root)


def _base_env() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if k != "GIT_DIR"}


def _have(binary: str) -> bool:
    from shutil import which

    return which(binary) is not None
