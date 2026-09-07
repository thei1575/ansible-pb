# Inventory resolution

pb selects one inventory for each session. That selection supplies
`group_vars`, group vaults, the limit picker, and the Status host list.

Explicit Ansible inventory settings take precedence. Repository discovery is
used when none of those settings provides a path.

## The precedence

<div class="annotate" markdown>

| # | Source | Doctor calls it | `-i` passed on? |
|---|---|---|---|
| 1 | `-i` / `--inventory` | `from -i` | :material-check: yes |
| 2 | `$ANSIBLE_INVENTORY` | `from $ANSIBLE_INVENTORY` | :material-close: no (1) |
| 3 | `[defaults] inventory` in `ansible.cfg` | `from ansible.cfg` | :material-close: no (1) |
| 4 | Found by looking around the repo | `found in the repo` | :material-check: yes |
| 5 | `inventories/production` | `pb's default - nothing named one` | :material-check: yes |

</div>

1.  Ansible resolves these two itself.

The first three are Ansible's own order. A path any of them names is used **even
if it does not exist**, because a misconfiguration is worth reporting rather
than papering over - [Doctor](../guide/doctor.md) fails the `inventory path`
check and says `- does not exist`.

## When pb passes `-i`

This is the subtle part, and it exists so that the host list pb shows you before
an apply is the one Ansible will actually use.

- When the path came from **`$ANSIBLE_INVENTORY` or `ansible.cfg`**, Ansible
  already knows it. pb passes nothing. Both of those accept a *comma-separated
  list* of sources, and passing `-i` would flatten a multi-source setting down
  to its first entry - silently changing which hosts a run touches.
- When the path came from **`-i`, from looking around, or from pb's default**,
  Ansible would not find it on its own, so pb passes `-i <path>` to every
  `ansible-playbook`, `ansible-inventory` and `--list-hosts` invocation it
  makes.

pb itself only ever displays **one** inventory, so with a multi-source setting
it shows and derives `group_vars` from the *first* source. Ansible still sees
the whole list, because pb passed nothing.

## Looking around

When nothing names an inventory, pb searches the repository root in this order
and takes the first hit.

**Directories**, in order: `inventories/`, then `inventory/`.

For each, pb looks at its subdirectories:

- Subdirectories named `group_vars` or `host_vars` are **not** environments.
- If what remains is empty - a flat `inventories/` holding `hosts.yml` and
  `group_vars/` - the directory itself is the inventory.
- Otherwise each remaining subdirectory is an environment, and pb takes the
  *environment* rather than its parent, because that is where `group_vars`
  lives. Merging every environment into one view is never what you meant.
- Among several environments it prefers `production`, `prod`, `main`, then
  `default`, in that order. Failing all four it takes the first
  alphabetically.

**Files** at the repository root, if no directory matched, in order:

`hosts.yml`, `hosts.yaml`, `hosts.ini`, `hosts`, `inventory.yml`,
`inventory.yaml`, `inventory.ini`

### The default of last resort

If the repository has nothing to find, pb settles on `inventories/production`
and reports it as `pb's default - nothing named one`. That path very likely does
not exist, and Doctor says so - naming a path that does not exist is more useful
than naming none.

## Worked examples

=== "ansible.cfg says so"

    ```ini title="ansible.cfg"
    [defaults]
    inventory = inventories/production
    ```

    ```
    inventory path   ✔ ok   inventories/production (from ansible.cfg)
    ```

    pb passes no `-i`. `group_vars` is
    `inventories/production/group_vars/`.

=== "Several environments, nothing configured"

    ```
    inventories/
      production/hosts.yml
      staging/hosts.yml
    ```

    ```
    inventory path   ✔ ok   inventories/production (found in the repo)
    ```

    `production` wins by preference. pb passes
    `-i inventories/production`. Switch with `pb -i inventories/staging`.

=== "A flat inventory directory"

    ```
    inventories/
      hosts.yml
      group_vars/
    ```

    ```
    inventory path   ✔ ok   inventories (found in the repo)
    ```

    Nothing under `inventories/` is an environment - `group_vars` is
    excluded by name - so the directory itself is the inventory.

=== "A single file at the root"

    ```
    hosts.ini
    group_vars/
    ```

    ```
    inventory path   ✔ ok   hosts.ini (found in the repo)
    ```

    For a *file* inventory, `group_vars` is taken from beside it - the
    file's parent directory - exactly as Ansible resolves it.

=== "A multi-source ansible.cfg"

    ```ini title="ansible.cfg"
    [defaults]
    inventory = inventories/production,inventories/edge
    ```

    ```
    inventory path   ✔ ok   inventories/production (from ansible.cfg)
    ```

    pb shows and derives `group_vars` from the first source and passes no
    `-i`, so Ansible still merges both.

=== "A path that does not exist"

    ```bash
    pb -i inventories/dr
    ```

    ```
    inventory path   ✘ fail   inventories/dr (from -i) - does not exist
    ```

    pb does not fall back. You asked for that path; it says it is not
    there.

## How `group_vars` is derived

Once the inventory is settled, `group_vars` follows mechanically:

| Inventory is | `group_vars` is |
|---|---|
| a directory | `<inventory>/group_vars/` |
| a file | `<inventory's parent>/group_vars/` |

That is how Ansible resolves it, and it is why switching inventory with `-i`
switches the [Vault](../guide/vault.md) tab's contents too.

## Reproducing pb's answer by hand

If pb and Ansible seem to disagree, the inventory line in Doctor names pb's
answer. Ansible's own is:

```bash
ansible-inventory --list --output /dev/null -vvv 2>&1 | grep -i 'parsed\|inventory'
```

They should agree. If they do not, the usual cause is an `ANSIBLE_CONFIG` or
`ANSIBLE_INVENTORY` exported in one shell and not the other.

!!! note "The test suite clears `$ANSIBLE_INVENTORY`"

    `Repo.discover` reads the environment, so pb's own tests clear that
    variable in an autouse fixture - a developer who has it exported must not
    get different results from CI. Account for this when
    [contributing](../project/contributing.md).
