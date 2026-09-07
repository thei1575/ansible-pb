# Status

A read-only health probe of every host in the inventory, over SSH, without
Ansible. One round trip per host, run in parallel, so a slow box does not hold
up the fleet.

| Column | What it shows |
|---|---|
| Host | The inventory hostname |
| State | `healthy`, `degraded`, `unreachable`, `local`, or `unknown` until you probe |
| Uptime | Shortened to the two largest units — `14w 4d` |
| Load | The three load averages |
| Disk | Used/total on `/`, red at 90% or more |
| Memory | Used/total |
| Notes | The one-line "what is wrong here": failed units, a full disk, a pending reboot, the count of pending updates |

A host counts as **degraded** rather than healthy if it has a failed systemd
unit or `/` is 90% full or more.

The detail pane adds the OS and kernel, the running service count, pending
updates, whether a reboot is required, the failed units by name, every running
container with its status, and the expiry date of each certificate it found.

`r` re-probes. `s` opens an SSH session to the selected host.

## What the probe actually runs

A fixed shell script, fed to `ssh <host>` on stdin so nothing has to survive
shell quoting. It reads and nothing else:

* `/etc/os-release`, `uname -r`, `uptime`, `/proc/loadavg`
* `df -h /`, `free -h`
* `/var/run/reboot-required`, `apt-get -s upgrade` (simulated — it changes
  nothing)
* `systemctl list-units --state=failed`, and a count of running services
* `docker ps`
* `openssl x509 -enddate` on `/etc/letsencrypt/live/<fqdn>/cert.pem`, for each
  host variable whose name ends in `_fqdn`

Anything unavailable is simply omitted, so a host without Docker, systemd or
apt reports what it has and skips the rest.

## Connection settings

The probe uses your existing SSH config, keys and agent; pb never handles a
password. It connects as `ansible_user` (or `root`) with `BatchMode=yes`,
`ConnectTimeout=8` and `StrictHostKeyChecking=accept-new`, passed as `-o`
flags — so a host key pb has not seen before is accepted and pinned on the
first probe rather than prompting, and a host that does not answer within 45
seconds is reported as unreachable rather than hanging the tab. Because `-o` takes precedence over `~/.ssh/config`, a stricter
setting there will not override them; if that trade-off does not suit you,
please [open an issue](https://github.com/thei1575/ansible-pb/issues).

A host with `ansible_connection: local`, or named `localhost`, is listed as
`local` and not probed — there is nothing to reach over SSH.
