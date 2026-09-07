# pb

A terminal console for an Ansible repository. Run playbooks, read the resolved
inventory, probe hosts over SSH, manage per-group vaults, and keep a record of
everything you applied — without leaving the terminal.

pb does not reimplement Ansible. It shells out to `ansible-playbook`,
`ansible-inventory` and `ansible-vault`, and always shows you the exact command
before it runs.

```bash
uv tool install git+https://github.com/thei1575/ansible-pb
cd ~/my-ansible-repo
pb
```

[Install pb](install.md){ .md-button .md-button--primary }
[What pb expects in your repo](repository.md){ .md-button }

## The tabs

| Tab | What it is for |
|---|---|
| [Playbooks](tabs/playbooks.md) | Run, dry-run or syntax-check anything, with `--tags`/`--limit` pickers |
| [Inventory](tabs/inventory.md) | Hosts, groups, resolved vars, ping, facts, ssh |
| [Status](tabs/status.md) | Live health per host over ssh: uptime, disk, failed units, containers, cert expiry |
| [Roles](tabs/roles.md) | Task files, defaults, and which playbooks use each role |
| [Vault](tabs/vault.md) | View, edit, create and rekey the per-group vaults |
| [History](tabs/history.md) | Every run pb has made, with its output kept |
| [Doctor](tabs/doctor.md) | Preflight over the whole repo |

Press `1`–`7` to jump between them, and `?` inside pb for the
[full key map](reference/keys.md).

## What it does that a Makefile cannot

**It shows the blast radius.** Applying resolves the real host list through
`--list-hosts` and names the hosts and addresses before you confirm, rather
than showing you a pattern.

**It keeps a record.** Every run is written to `.pb/runs/` in the repo —
command, tags, exit code, recap, the commit it ran against, and the full
output — so "what did I apply, and did it work" has an answer.

**It marks uncommitted work.** A yellow `●` on a playbook or role means its
files differ from `HEAD`; `ctrl+g` shows the diff.

The pane on the right always shows the exact `ansible-playbook` command your
current options produce, so nothing runs that you have not read first.

## What it does not do

* It does not parse Ansible semantics itself. If Ansible cannot resolve your
  inventory, neither can pb — and the [Doctor](tabs/doctor.md) tab will say so.
* It does not install or manage Ansible. pb drives whatever `ansible` is
  already on your `PATH`.
* It makes no network connections of its own: no telemetry, no update check.
  The only traffic is Ansible's and SSH's. See [Security](security.md).
