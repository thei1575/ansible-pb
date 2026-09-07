# Command line

pb's command line is small on purpose: everything else is a keypress inside.

```
usage: pb [-h] [-i PATH] [--no-update-check] [--version] [path]
```

## Arguments

### `path`

A directory *inside* the Ansible repository. Defaults to the working directory.

pb walks up from it to the nearest `ansible.cfg` and treats that directory as
the repository root, so any subdirectory works:

```bash
pb                              # the working directory
pb ~/my-ansible-repo            # an explicit repo
pb ~/my-ansible-repo/roles/web  # also fine — pb walks up
```

### `-i`, `--inventory PATH`

The inventory file or directory to read. Relative paths resolve against the
repository root; `~` is expanded.

```bash
pb -i inventories/staging
pb -i hosts.ini
pb ~/my-ansible-repo -i inventories/dr
```

This takes precedence over everything, is honoured even if the path does not
exist — [Doctor](../guide/doctor.md) reports that rather than falling back — and
causes pb to pass `-i` through to `ansible-playbook` and `ansible-inventory`, so
what pb shows you is what Ansible will use.

Without it, pb resolves the inventory the way Ansible does. See
[Inventory resolution](inventory-resolution.md).

### `--no-update-check`

Stops pb asking GitHub for a newer release when it starts. `PB_NO_UPDATE_CHECK=1`
does the same for every invocation.

<kbd>ctrl</kbd>+<kbd>u</kbd> still checks when you ask it to — the flag turns off
pb going to look on its own, not the feature. See [Updating](updates.md).

### `--version`

Prints `pb <version>` and exits.

### `-h`, `--help`

Prints the usage above and exits.

## Exit codes

| Code | Means |
|---|---|
| `0` | pb ran and you quit it |
| `2` | `path` is not a directory, or there is no `ansible.cfg` in it or any parent |

pb's own exit code says nothing about the runs you made inside it — those are in
the [History](../guide/history.md) tab, each with Ansible's exit code verbatim.

Both `2` cases print an explanation to stderr:

```
pb: /home/you/src is not a directory
```

```
pb: no ansible.cfg in /home/you/src or any parent directory.
pb runs inside an Ansible repository — cd into one, or give it a path.
```

## Environment

pb reads three variables of its own, and sets several for the Ansible processes
it spawns.

### Read by pb

| Variable | Effect |
|---|---|
| `ANSIBLE_INVENTORY` | Second in the inventory precedence, after `-i`. A comma-separated list is accepted; pb shows the first source and leaves the whole list to Ansible |
| `EDITOR` | Used by `ansible-vault edit` from the [Vault](../guide/vault.md) tab — pb does not read it directly, Ansible does |
| `PB_NO_UPDATE_CHECK` | Anything but empty, `0`, `false` or `no` turns the startup [update check](updates.md) off |
| `XDG_CONFIG_HOME` | Where `pb/update.json` lives. Defaults to `~/.config` |

### Set for Ansible

Every run pb launches gets these on top of your environment:

| Variable | Value | Why |
|---|---|---|
| `ANSIBLE_FORCE_COLOR` | `1` | pb allocates a pty so Ansible keeps its colour; this makes sure |
| `PY_COLORS` | `1` | same, for anything Python-side |
| `TERM` | `xterm-256color` | the pty pb allocates |
| `COLUMNS` | the pane width | so Ansible's own wrapping matches the pane |
| `ANSIBLE_NOCOWS` | `1` | nothing in a pb run is interactive, and a prompt would deadlock the pty reader |

Anything else in your environment is passed through untouched — your
`ANSIBLE_CONFIG`, your `SSH_AUTH_SOCK`, your `ANSIBLE_VAULT_PASSWORD_FILE`.

## Running as a module

```bash
python -m pb ~/my-ansible-repo
```

Identical to `pb`, and useful when you have installed pb into a virtualenv
without putting its `bin/` on `PATH`.
