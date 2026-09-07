# Command line

pb has almost no command line: it is a console, and everything else happens
inside it.

```
usage: pb [-h] [-i PATH] [--version] [path]

A terminal console for an Ansible repository.

positional arguments:
  path                  a directory inside the Ansible repo (default: the
                        working directory)

options:
  -h, --help            show this help message and exit
  -i, --inventory PATH  the inventory file or directory to read (default:
                        whatever ansible.cfg says, else the one pb can find in
                        the repo)
  --version             show program's version number and exit
```

## `path`

A directory inside the Ansible repository. pb walks up from it to the nearest
`ansible.cfg`, which marks the root. Defaults to the working directory.

```bash
pb                      # the repo you are standing in
pb ~/my-ansible-repo    # somewhere else
```

## `-i` / `--inventory`

The inventory to read for this session, absolute or relative to the repo root.
It wins over `$ANSIBLE_INVENTORY` and `ansible.cfg`, and pb then passes the
same `-i` on to `ansible-playbook` and `ansible-inventory` so Ansible agrees.
See [Your repository](../repository.md).

```bash
pb -i inventories/staging
```

## Exit codes

`0`
:   pb ran and you quit it.

`2`
:   The path is not a directory, or there is no `ansible.cfg` in it or any
    parent — pb has no repository to show.

## Environment

`ANSIBLE_INVENTORY`
:   Read as Ansible reads it, second in precedence after `-i`.

`EDITOR`
:   Used by `ansible-vault edit` from the [Vault](../tabs/vault.md) tab.

Everything else is Ansible's own environment: pb shells out in the repo root
with your environment untouched.

## Module form

`python -m pb` works the same as `pb`.
