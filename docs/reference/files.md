# Files pb touches

pb is a console over your own repository. It reads a lot and writes almost
nothing. This page is the complete list, on your machine and on your hosts.

## Reads, in your repository

| Path | For |
|---|---|
| `ansible.cfg` | marks the repository root; `[defaults] inventory` is read from it |
| `playbooks/*.yml` | the [Playbooks](../guide/playbooks.md) tab |
| `roles/*/` | the [Roles](../guide/roles.md) tab — `tasks/*.yml`, `defaults/main.yml`, and which of `handlers`, `templates`, `files`, `vars`, `meta` exist |
| the resolved inventory | via `ansible-inventory --list` |
| `<group_vars>/*/vault.yml` | the [Vault](../guide/vault.md) tab — only the first line is read directly, to check the `$ANSIBLE_VAULT` header |
| `.vault_pass` | its existence and mode, for [Doctor](../guide/doctor.md). pb does not read the contents — Ansible does |
| `collections/ansible_collections/*/*` | the collections Doctor lists |
| `.git` | via `git`, for the `●` marker, the changes viewer, and the commit recorded with each run |

## Writes, in your repository

Two things, both in the repository root.

### `.pb/runs/`

Every run pb launches, as a pair of files named by local timestamp:

```
.pb/runs/20260907-142233.json   # command, tags, exit code, recap, commit, hosts
.pb/runs/20260907-142233.log    # the complete output, ANSI stripped
```

pb prunes to the most recent 300 pairs and never removes the directory itself.
A failure to write a record is swallowed — losing history must not cost you the
run you are watching.

### `pb-<label>-<timestamp>.log`

Written only when you press <kbd>s</kbd> in a run view. The label is the run's
own, with anything outside `[A-Za-z0-9-_]` replaced by `-`.

!!! danger "Gitignore both"

    ```bash
    echo '.pb/' >> .gitignore
    echo 'pb-*.log' >> .gitignore
    ```

    Run records hold the **complete** Ansible output and are not scrubbed —
    anything a task printed is in there. Committing them is how output that was
    only ever meant for your terminal ends up in a shared repository's history.

### Transiently, during a vault create

<kbd>n</kbd> in the Vault tab writes `.pb-new-vault.yml` in the repository root,
encrypts it to the target path with `ansible-vault encrypt --output`, and
removes it — whether or not the encryption succeeded.

## Writes, in your home directory

### `~/.config/pb/update.json`

The only file pb writes outside the repository, and the only state it keeps
between runs. Two keys, both about the [update check](updates.md) and neither
about your repository:

```json
{
  "last_check": 1789050153.4,
  "skipped": "0.2.0"
}
```

`last_check` is when pb last asked GitHub, so it asks at most once a day.
`skipped` is a version you declined, so it is never offered again. Delete the
file and pb checks on the next start and offers whatever it finds; a failure to
write it is swallowed, the same as a run record.

`$XDG_CONFIG_HOME` is honoured when set.

## What pb never writes

- An encrypted file, except by invoking `ansible-vault` itself.
- Anything under `playbooks/`, `roles/`, or the inventory.
- Anything outside the repository root and `~/.config/pb/`, other than what
  Ansible and your editor do on their own.
- A cache of anything it read from your repository.

## On your hosts

Two things reach a host, and only when you ask.

**Whatever the playbook does.** pb hands `ansible-playbook` a command line and
shows it to you first. Everything past that point is Ansible's and yours.

**The Status probe**, which is read-only. One fixed shell script piped to
`ssh <host> bash -s`, running only:

```
uname -r · cat /etc/os-release · uptime -p · cut /proc/loadavg
df -h / · free -h · test -f /var/run/reboot-required
apt-get -s -o Debug::NoLocking=true upgrade
systemctl list-units --state=failed · systemctl list-units --type=service
docker ps · openssl x509 -enddate -noout
```

Nothing in it changes a host. The `apt-get` is a simulation (`-s`) and takes no
dpkg lock. See [Status](../guide/status.md).

## Network

pb makes **no network connections of its own**. No telemetry, no update check,
no outbound anything. The only traffic is Ansible's and SSH's, on your
credentials.

## Processes pb spawns

The complete list of external commands, so you can audit it against your own
`PATH`:

| Command | When |
|---|---|
| `ansible --version` | Doctor |
| `ansible-playbook <file> [options]` | apply, dry run, syntax check, Doctor's per-playbook check |
| `ansible-playbook <file> --list-tags` | the tags picker |
| `ansible-playbook <file> --list-hosts` | the apply confirmation |
| `ansible-inventory --list` | the Inventory tab, and everything derived from it |
| `ansible <host> -m ping` | <kbd>p</kbd> in Inventory |
| `ansible <host> -m setup` | <kbd>f</kbd> in Inventory |
| `ansible-vault view` | <kbd>v</kbd> in Vault, and Doctor |
| `ansible-vault edit` | <kbd>e</kbd> in Vault |
| `ansible-vault encrypt --output` | <kbd>n</kbd> in Vault |
| `ansible-vault rekey` | <kbd>k</kbd> in Vault |
| `ansible-lint --version` | Doctor — the version only; pb never lints |
| `ssh` | the Status probe, and <kbd>s</kbd> in Inventory and Status |
| `git status`, `git diff`, `git rev-parse` | the `●` marker, the changes viewer, the commit per run |

Runs get a pty and their own process group, so cancelling with
<kbd>ctrl</kbd>+<kbd>c</kbd> kills the forks Ansible spawned and not just
Ansible itself. Read-only lookups get a plain pipe, stderr merged into
stdout, and a 120-second timeout — 30 seconds for the `--version` probes and
`ansible-vault view`, 10 for `git rev-parse`.
