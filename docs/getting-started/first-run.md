# First run

```bash
cd ~/my-ansible-repo
pb
```

That is the whole invocation. pb walks up from the working directory to the
nearest `ansible.cfg` and treats that directory as the repository root. You can
also point it at one from anywhere:

```bash
pb ~/my-ansible-repo
```

If there is no `ansible.cfg` in the given directory or any parent, pb says so
and exits `2` rather than guessing:

```
pb: no ansible.cfg in /home/you/src or any parent directory.
pb runs inside an Ansible repository — cd into one, or give it a path.
```

## Start at Doctor

The first thing worth doing in a repo pb has not seen is press <kbd>7</kbd>.

[Doctor](../guide/doctor.md) runs a preflight over the whole repository: it
finds `ansible`, names the inventory it settled on and where that came from,
checks `group_vars` exists beside it, checks `.vault_pass` is present and
`0600`, decrypts every vault, counts the hosts, and syntax-checks every
playbook.

The inventory line is the important one. It tells you which inventory pb is
reading and why — which is the quickest way to confirm pb and Ansible agree
about your repo.

```
inventory path   ✔ ok     inventories/production (from ansible.cfg)
group_vars       ✔ ok     inventories/production/group_vars
vault password   ✔ ok     .vault_pass 0o600
inventory        ✔ ok     14 hosts in 6 groups
```

If that line is wrong, fix it there and not later — every other tab is derived
from it. See [Inventory resolution](../reference/inventory-resolution.md).

## Choosing an inventory

pb follows Ansible's own precedence, so a repo where Ansible already works
needs no configuring:

1. `-i` / `--inventory` on the command line
2. `$ANSIBLE_INVENTORY`
3. `[defaults] inventory` in `ansible.cfg`
4. failing all three, a look around the repo — preferring `inventories/production`

To pick a different one for this session:

```bash
pb -i inventories/staging
```

`group_vars` is then taken from beside whichever inventory won, the way Ansible
resolves it.

## Getting around

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>1</kbd>…<kbd>7</kbd> | Jump to a tab |
| <kbd>?</kbd> | The full key map, in pb |
| <kbd>ctrl</kbd>+<kbd>r</kbd> | Reload everything from disk |
| <kbd>ctrl</kbd>+<kbd>g</kbd> | The working-tree diff |
| <kbd>ctrl</kbd>+<kbd>p</kbd> | Command palette |
| <kbd>q</kbd> | Quit |

</div>

Each tab has its own verbs, and the footer only ever offers what the focused
tab can actually do. The [key map](../reference/keys.md) has all of them.

## Your first dry run

1. <kbd>1</kbd> for Playbooks, then move the cursor to a playbook.
2. <kbd>t</kbd> to pick tags, <kbd>l</kbd> to pick a limit — both lists come
   from Ansible, not from parsing YAML.
3. Read the pane on the right. It shows the exact `ansible-playbook` command
   your current options produce.
4. <kbd>c</kbd> for a dry run. pb adds `--check --diff` — a `--check` without
   `--diff` tells you almost nothing, so pb implies it rather than making the
   toggle a prerequisite.

The run opens full-screen and streams Ansible's output live, in colour.
<kbd>ctrl</kbd>+<kbd>c</kbd> cancels, <kbd>s</kbd> saves the log, <kbd>esc</kbd>
closes. When it finishes, the run is already in [History](../guide/history.md).

!!! tip "Nothing changes until you press `r`"

    <kbd>c</kbd> is `--check`, <kbd>s</kbd> is `--syntax-check`, and
    <kbd>enter</kbd> is a dry run. Only <kbd>r</kbd> applies, and it asks
    first — after resolving and showing you the real host list.

## Next

[Repository layout :octicons-arrow-right-24:](repository-layout.md){ .md-button .md-button--primary }
[The Playbooks tab :octicons-arrow-right-24:](../guide/playbooks.md){ .md-button }
