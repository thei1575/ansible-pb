# Repository layout

pb reads an existing Ansible repository and stores its own state under `.pb/`.

```
ansible.cfg                          # marks the repo root
playbooks/*.yml
roles/<role>/{tasks,defaults}/
<inventory>                          # whatever ansible.cfg says, or -i
<inventory>/group_vars/<group>/{main,vault}.yml
.vault_pass                          # gitignored, 0600
.pb/runs/                            # pb's own run records - gitignore this
```

## Fixed paths

`playbooks/` and `roles/` are the only paths pb assumes.

- **`playbooks/`** - every `*.yml` here becomes a row in the
  [Playbooks](../guide/playbooks.md) tab. The description column is the file's
  own header comment where it has one, and the first play's `name` otherwise.
- **`roles/`** - every directory here becomes a row in the
  [Roles](../guide/roles.md) tab, with its `tasks/` files, its
  `defaults/main.yml`, and the playbooks that reference it.

Everything else is resolved rather than assumed.

## The inventory

pb shows exactly one inventory at a time, and derives `group_vars` and the
vault list from it. Which one it uses is decided by Ansible's own precedence
first, and only then by looking around:

<div class="annotate" markdown>

| Origin | Doctor says | pb passes `-i`? |
|---|---|---|
| `-i` / `--inventory` | `from -i` | yes |
| `$ANSIBLE_INVENTORY` | `from $ANSIBLE_INVENTORY` | no (1) |
| `[defaults] inventory` in `ansible.cfg` | `from ansible.cfg` | no (1) |
| Found in the repo | `found in the repo` | yes |
| Nothing named one | `pb's default - nothing named one` | yes |

</div>

1.  Ansible resolves these two itself, and both accept a comma-separated list
    of sources. Passing `-i` would flatten a multi-source setting down to its
    first entry, so pb passes nothing and leaves it intact.

When nothing names an inventory, pb looks for `inventories/` then `inventory/`,
and failing those a `hosts.yml`, `hosts.yaml`, `hosts.ini`, `hosts`,
`inventory.yml`, `inventory.yaml` or `inventory.ini` at the root. The full rules
are in [Inventory resolution](../reference/inventory-resolution.md).

### Several environments

A repo laid out per environment works without configuration:

```
inventories/
  production/
    hosts.yml
    group_vars/
  staging/
    hosts.yml
    group_vars/
```

pb picks the *environment directory*, not its parent - that is where
`group_vars` lives, and merging every environment into one view is never what
you meant. Among several it prefers `production`, `prod`, `main` or `default`,
in that order, and otherwise takes the first alphabetically. Switch with:

```bash
pb -i inventories/staging
```

`group_vars/` and `host_vars/` directly under `inventories/` are not treated as
environments, so a flat `inventories/hosts.yml` + `inventories/group_vars/`
layout is read as one inventory.

## `group_vars` and the vaults

`group_vars` is always taken from beside whichever inventory won, exactly as
Ansible resolves it - `<inventory>/group_vars/` for a directory inventory, or
`<inventory's parent>/group_vars/` for a file.

The [Vault](../guide/vault.md) tab lists one entry per group directory that has
a vault file in it:

```
inventories/production/group_vars/
  all/
    main.yml
    vault.yml        # encrypted
  webservers/
    main.yml
    vault.yml
```

## `.vault_pass`

pb reads the vault password from the repository's `.vault_pass`, the same way
Ansible does through your `ansible.cfg`. Keep it `0600` and gitignored - Doctor
fails the check if the mode is anything else, and fails outright if the file is
missing, because nothing that touches a vault will run without it.

## Collections

If your repo vendors collections under `collections/ansible_collections/`,
Doctor lists what is installed. It does not install them for you.

## Local pb state

Exactly one thing: `.pb/` in the repository root.

```
.pb/runs/
  20260907-142233.json   # command, tags, exit code, recap, commit, hosts
  20260907-142233.log    # the full captured output, ANSI stripped
```

pb prunes to the most recent 300 records and never removes the directory
itself. See [Files pb touches](../reference/files.md) for everything pb reads
and writes, on your machine and on your hosts.
