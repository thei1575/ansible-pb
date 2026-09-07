# Your repository

pb is a console over a repository you already have. It reads a conventional
Ansible layout and configures nothing of its own.

## Finding the repo

pb walks up from the working directory to the nearest `ansible.cfg`. That file
marks the repo root; without one, pb exits and tells you so.

```bash
cd ~/my-ansible-repo && pb
```

You can also point it at a directory:

```bash
pb ~/my-ansible-repo
```

## Finding the inventory

For the inventory, pb follows Ansible's own precedence:

1. `-i` / `--inventory` on pb's own command line
2. `$ANSIBLE_INVENTORY`
3. `[defaults] inventory` in `ansible.cfg`

So if Ansible already works in your repo, pb reads the same inventory without
being told. Failing all three it looks around the repo, preferring
`inventories/production`, and also recognising `inventories/<env>/` under any
name, `inventory/`, and a `hosts.yml`, `hosts.ini` or `inventory.yml` at the
root.

To pick a different one for this session:

```bash
pb -i inventories/staging
```

A path that any of the first three sources names is honoured **even if it does
not exist** — a misconfiguration is worth reporting rather than papering over,
and the [Doctor](tabs/doctor.md) tab names the inventory pb settled on, where
that came from, and whether it is there. That is the quickest way to check pb
and Ansible agree.

!!! info "When pb passes `-i`, and when it does not"
    pb passes `-i` to `ansible-playbook` and `ansible-inventory` whenever the
    path came from somewhere Ansible would not look itself — so the host list
    pb shows before an apply is the one Ansible will use. When the path came
    from `ansible.cfg` or the environment, pb passes nothing and leaves a
    multi-source setting intact.

`group_vars` is taken from beside whichever inventory won, the way Ansible
resolves it, and the vaults are read from there too.

## The layout pb expects

```
ansible.cfg                          # marks the repo root
playbooks/*.yml
roles/<role>/{tasks,defaults}/
<inventory>                          # see above
<inventory>/group_vars/<group>/{main,vault}.yml
.vault_pass                          # gitignored, 0600
collections/ansible_collections/     # optional; Doctor lists what is installed
```

`playbooks/` and `roles/` are the two fixed names. Everything else follows
your `ansible.cfg`.

## What pb writes

pb writes in exactly two places, and only ever in your repo:

`.pb/runs/`
:   One record per run — a JSON sidecar plus the captured output. Pruned to the
    last 300 runs. See [History](tabs/history.md).

The vaults
:   Only by invoking `ansible-vault` itself, and only from the
    [Vault](tabs/vault.md) tab.

!!! warning "Add `.pb/` to your `.gitignore`"
    Run records contain the full Ansible output, which can include anything a
    task printed.
