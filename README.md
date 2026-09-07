# pb

A terminal console for an Ansible repository. Run playbooks, read the resolved
inventory, probe hosts over SSH, manage per-group vaults, and keep a record of
everything you applied — without leaving the terminal.

pb does not reimplement Ansible. It shells out to `ansible-playbook`,
`ansible-inventory` and `ansible-vault`, and always shows you the exact command
before it runs.

## Install

```bash
uv tool install git+https://github.com/thei1575/ansible-pb
```

or, from a clone:

```bash
uv tool install .
```

`pipx install git+https://github.com/thei1575/ansible-pb` works too. Not on
PyPI yet. pb needs Python 3.11+ and a POSIX terminal (macOS or Linux) — it
allocates a pty so Ansible keeps its colour.

Ansible itself is deliberately *not* a dependency: pb drives whatever `ansible`
is already on your `PATH`, so it never interferes with how you install it.

## Use

```bash
cd ~/my-ansible-repo
pb
```

pb finds the repo by walking up from the working directory to the nearest
`ansible.cfg`. You can also point it at one:

```bash
pb ~/my-ansible-repo
```

Press `?` inside for the full key map.

| Tab | What it is for |
|---|---|
| Playbooks | Run, dry-run or syntax-check anything, with `--tags`/`--limit` pickers |
| Inventory | Hosts, groups, resolved vars, ping, facts, ssh |
| Status | Live health per host over ssh: uptime, disk, failed units, containers, cert expiry |
| Roles | Task files, defaults, and which playbooks use each role |
| Vault | View, edit, create and rekey the per-group vaults |
| History | Every run pb has made, with its output kept |
| Doctor | Preflight over the whole repo |

## What it does that a Makefile cannot

* **It shows the blast radius.** Applying resolves the real host list through
  `--list-hosts` and names the hosts and addresses before you confirm, rather
  than showing you a pattern.
* **It keeps a record.** Every run is written to `.pb/runs/` in the repo —
  command, tags, exit code, recap, the commit it ran against, and the full
  output — so "what did I apply, and did it work" has an answer.
* **It marks uncommitted work.** A yellow `●` on a playbook or role means its
  files differ from `HEAD`; `ctrl+g` shows the diff.

The pane on the right always shows the exact `ansible-playbook` command your
current options produce, so nothing runs that you have not read first.

## Secrets

`ansible-inventory` decrypts the vaults to resolve variables, so the Inventory
tab masks anything whose name looks like a credential (`*_password`, `*_token`,
`*_key`, `secret`, `salt`, …) until you press `R`. Nothing is ever written back
except through `ansible-vault` itself.

Add `.pb/` to the repo's `.gitignore` — run records contain full Ansible output.

## Repo layout it expects

pb reads a conventional layout:

```
ansible.cfg                          # marks the repo root
playbooks/*.yml
roles/<role>/{tasks,defaults}/
inventories/production/hosts.yml
inventories/production/group_vars/<group>/{main,vault}.yml
.vault_pass                          # gitignored, 0600
```

The inventory path is currently fixed at `inventories/production`. If your repo
puts it elsewhere, that is the one thing to change — see `Repo` in
[`src/pb/meta.py`](src/pb/meta.py).

## Development

```bash
uv sync
uv run pb ~/my-ansible-repo
```

## Licence

MIT — see [LICENSE](LICENSE).
