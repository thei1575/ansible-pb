# Install

pb needs **Python 3.11+** and a POSIX terminal (macOS or Linux) — it allocates
a pty so Ansible keeps its colour.

## With uv

```bash
uv tool install git+https://github.com/thei1575/ansible-pb
```

Or, from a clone:

```bash
uv tool install .
```

## With pipx

```bash
pipx install git+https://github.com/thei1575/ansible-pb
```

!!! note "Not on PyPI yet"
    pb installs from git for now. The distribution name is `ansible-pb`; the
    command it installs is `pb`.

## Ansible is deliberately not a dependency

pb drives whatever `ansible` is already on your `PATH`, so installing pb never
interferes with how you install Ansible — a system package, a virtualenv, a
`uv tool`, whatever you already have.

It needs three of Ansible's own commands to be runnable in the repo:

* `ansible-playbook` — running, dry-running and syntax-checking
* `ansible-inventory` — the Inventory tab and the resolved variables
* `ansible-vault` — viewing, editing, creating and rekeying vaults

The [Doctor](tabs/doctor.md) tab checks `ansible --version` first, so a broken
or missing installation shows up there rather than as a failed run.

## Upgrade

Installed from git, so an upgrade means re-fetching the repository:

```bash
uv tool upgrade ansible-pb --reinstall
```

```bash
pipx upgrade ansible-pb
```

`uv tool install` with the same URL works too, and is what to use if you want
to pin a tag or a branch — `git+https://github.com/thei1575/ansible-pb@v0.1.0`.

## Check it works

```bash
pb --version
cd ~/my-ansible-repo && pb
```

If pb exits complaining about `ansible.cfg`, it did not find a repository —
see [Your repository](repository.md).
