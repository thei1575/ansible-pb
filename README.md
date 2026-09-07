# pb

[![CI](https://github.com/thei1575/ansible-pb/actions/workflows/ci.yml/badge.svg)](https://github.com/thei1575/ansible-pb/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-334155)](https://www.python.org/downloads/)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-c47f17)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-pb-c47f17)](https://thei1575.github.io/ansible-pb/)

**Run control for Ansible.**

pb is the operator interface for an Ansible repository. It brings playbook
execution, resolved inventory, host status, vault access, repository checks,
run history, and repository-specific extensions into one terminal application.

Before an apply, pb resolves the target hosts and presents the complete
`ansible-playbook` command for review. After the run, it stores the command,
output, result, and Git commit under `.pb/runs/`.

```text
 Playbooks  Inventory  Status  Roles  Vault  History  Doctor  Plugins
┌──────────────────────────────────────────┬─────────────────────────────────┐
│ ● site.yml        Everything, in order   │ COMMAND                         │
│   webservers.yml  nginx and certificates │ ansible-playbook                │
│   database.yml    postgres and backups   │     playbooks/webservers.yml    │
│   bootstrap.yml   A fresh host, once     │     --tags certs --limit web01  │
│                                          │     --diff                      │
│                                          │                                 │
│                                          │ HOSTS                           │
│                                          │ web01  10.0.4.11                │
└──────────────────────────────────────────┴─────────────────────────────────┘
 tags certs  limit web01  diff on  -v 0
 r Run  c Dry run  s Syntax  t Tags  l Limit  d Diff  ? Help  q Quit
```

## Operating model

| Stage | pb provides |
|---|---|
| Inspect | Playbooks, roles, resolved host variables, group membership, and repository health |
| Scope | Tag and host selectors populated from Ansible's output |
| Review | The complete command, target hosts, addresses, and uncommitted-change count |
| Execute | Apply, check mode, syntax check, ad-hoc ping, facts, SSH, and vault commands |
| Record | Full output, exit code, recap, options, timestamp, and Git commit for every run |
| Extend | Plugin tabs, actions, run hooks, Doctor checks, detail sections, and status data |

`pb` invokes the Ansible installation available on `PATH`. Inventory, tag,
host, and vault behaviour comes from the same Ansible commands, configuration,
plugins, and credentials used at the shell.

## Install

pb requires Python 3.11 or newer, Ansible on `PATH`, and a POSIX terminal on
macOS or Linux. Current releases are installed from GitHub.

```bash
uv tool install git+https://github.com/thei1575/ansible-pb
```

`pipx` is also supported:

```bash
pipx install git+https://github.com/thei1575/ansible-pb
```

For development installs:

```bash
git clone https://github.com/thei1575/ansible-pb
cd ansible-pb
uv tool install .
```

## Start a repository session

Run `pb` anywhere under the repository root:

```bash
cd ~/my-ansible-repo
pb
```

You can also pass a repository path or choose an inventory for the session:

```bash
pb ~/my-ansible-repo
pb ~/my-ansible-repo -i inventories/staging
```

The nearest `ansible.cfg` marks the repository root. Inventory selection uses
this order:

1. `-i` or `--inventory`
2. `$ANSIBLE_INVENTORY`
3. `[defaults] inventory` in `ansible.cfg`
4. a recognised inventory inside the repository
5. `inventories/production`

Open **Doctor** after startup to verify the selected inventory, password file,
collections, vaults, plugins, playbook syntax, and local toolchain.

## Plugins

Plugins add repository-specific operations to pb. A plugin can provide tabs,
key actions, command-palette entries, Doctor checks, run hooks, detail-pane
sections, and status-bar data.

Install and manage plugins from the command line:

```bash
pb plugin install owner/pb-terraform
pb plugin install owner/pb-thing@v1.2
pb plugin list
pb plugin disable pb-thing
```

The **Plugins** tab provides install, update, enable, disable, and remove
actions inside pb. Press <kbd>8</kbd> to open it.

Create or link a plugin during development:

```bash
pb plugin new pb-mine
pb plugin link .
pb plugin doctor
```

Plugins are Python code loaded into the pb process with the current user's
permissions. They have no sandbox. Hook errors disable the affected plugin for
the session and appear in Doctor. Use `pb --no-plugins` to start a session with
plugin loading disabled.

See the [plugin operator guide](https://thei1575.github.io/ansible-pb/guide/plugins/),
[build your first plugin](https://thei1575.github.io/ansible-pb/plugins/quickstart/),
or use the [plugin API reference](https://thei1575.github.io/ansible-pb/reference/writing-plugins/)
and [plugin authoring reference](https://thei1575.github.io/ansible-pb/reference/writing-plugins/).

## Repository contract

pb works with this layout:

```text
ansible.cfg
playbooks/*.yml
roles/<role>/{tasks,defaults}/
<inventory>
<inventory>/group_vars/<group>/{main,vault}.yml
.vault_pass
```

`playbooks/` and `roles/` have fixed names. The inventory may come from
`ansible.cfg`, a command-line path, an environment variable, or one of the
recognised repository layouts described in the
[inventory resolution reference](https://thei1575.github.io/ansible-pb/reference/inventory-resolution/).

Add `.pb/` and `.vault_pass` to the managed repository's `.gitignore`:

```gitignore
.pb/
.vault_pass
```

Run records contain complete Ansible output and may contain secrets printed by
a task. The Inventory view masks credential-shaped variables on screen until
they are explicitly revealed.

## Update policy

Once a day, pb checks the GitHub releases endpoint for a newer version. The
update dialog contains the release notes and installation command. Installation
only begins after confirmation.

Use <kbd>ctrl</kbd>+<kbd>u</kbd> for a manual check. Disable the startup check
with either form:

```bash
pb --no-update-check
export PB_NO_UPDATE_CHECK=1
```

The [update reference](https://thei1575.github.io/ansible-pb/reference/updates/)
documents the request, local state file, and installer detection.

## Development

```bash
uv sync
uv run pb ~/my-ansible-repo
uv run ruff check .
uv run pytest
uv run --group docs mkdocs serve
```

The test suite builds temporary Ansible repositories and local plugin sources.
Ansible and network access are not required for tests. CI covers Python 3.11,
3.12, and 3.13, with an additional macOS run for pty handling.

Repository architecture and contribution rules are documented in
[CONTRIBUTING.md](.github/CONTRIBUTING.md). Security reports belong in GitHub's
[private vulnerability reporting](https://github.com/thei1575/ansible-pb/security/advisories/new)
or the address listed in [SECURITY.md](.github/SECURITY.md).

## Licence

[MIT](LICENSE)
