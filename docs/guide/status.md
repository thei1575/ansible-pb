# Status

<kbd>3</kbd>

Status collects a compact health report over SSH in one round trip per host.
The probe reads host state directly and makes no changes.

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>r</kbd> | Probe every host in the inventory |
| <kbd>s</kbd> | SSH into the selected host |

</div>

Opening the tab starts a probe the first time, and only the first time. After
that nothing touches your hosts until you press <kbd>r</kbd>.

## Collected data

One compound shell script is piped to `ssh <host> bash -s` on stdin - so
nothing has to survive shell quoting - and it emits `key=value` lines. Anything
unavailable on a given host is simply omitted, which keeps the probe portable
across whatever a host happens to run.

| Column | Read with |
|---|---|
| OS | `/etc/os-release` (`PRETTY_NAME`) |
| Kernel | `uname -r` |
| Uptime | `uptime -p`, shortened to e.g. `14w 4d` |
| Load | the first three fields of `/proc/loadavg` |
| Disk | `df -h /` - used/total and the percentage |
| Memory | `free -h` |
| Reboot | whether `/var/run/reboot-required` exists |
| Updates | `apt-get -s upgrade`, counting `^Inst` lines |
| Failed units | `systemctl list-units --state=failed` |
| Services | the count of running `.service` units |
| Containers | `docker ps` - name and status |
| Certificates | `openssl x509 -enddate` on `/etc/letsencrypt/live/<fqdn>/cert.pem` |

The certificate check needs to know which names to look for. pb takes them from
the host's own resolved variables: every variable whose name ends in `_fqdn`
and whose value is a non-empty string. So a host with
`web_fqdn: shop.example.com` gets that certificate's expiry read, and a host
with no `*_fqdn` variables gets no certificate rows.

!!! success "It only ever reads"

    `uname`, `df`, `free`, `systemctl list-units`, `docker ps`,
    `openssl x509 -enddate`. Nothing in the script changes a host. The
    `apt-get upgrade` is `-s` - a simulation - and it also passes
    `-o Debug::NoLocking=true` so it does not contend for the dpkg lock.

## The notes column

The one-line "what is wrong here" summary, in the order it matters:

| Note | When |
|---|---|
| `<unit> failed` | any unit is in the failed state - one entry per unit, red |
| `disk NN%` | the root filesystem is 90% full or more, red |
| `reboot pending` | `/var/run/reboot-required` exists, yellow |
| `N updates` | `apt-get -s upgrade` counted any, cyan |
| `-` | none of the above |

A host counts as **healthy** when it is reachable, has no failed units, and is
below 90% disk. After a probe, pb notifies you once: unreachable hosts as an
error, hosts needing attention as a warning, and otherwise "all hosts healthy".

## How it connects

pb uses your existing SSH configuration, keys and agent. It never handles a
password. The connection is made with:

```bash
ssh -o BatchMode=yes \
    -o ConnectTimeout=8 \
    -o StrictHostKeyChecking=accept-new \
    <ansible_user>@<address> bash -s
```

`<ansible_user>` is the host's `ansible_user` variable or `root`;
`<address>` is its `ansible_host` or its inventory name.

Hosts are probed in parallel, up to eight at a time, so one slow host does not
hold up the fleet. Each has a 45-second budget.

!!! warning "`-o` flags win over `~/.ssh/config`"

    `BatchMode` and `StrictHostKeyChecking` are passed on the command line,
    which takes precedence over your config file. A host key pb has not seen
    before is therefore **accepted and pinned on the first probe** rather than
    prompting, and a stricter setting in `~/.ssh/config` will not override
    that. If that trade-off does not suit you, please
    [open an issue](https://github.com/thei1575/ansible-pb/issues).

## When a host does not answer

pb always returns a status, never an exception, and says which kind of nothing
it got:

| Shown | Means |
|---|---|
| `local connection - nothing to probe` | the host is `localhost`, or has `ansible_connection: local` |
| `ssh not found on PATH` | no `ssh` binary |
| `no answer within 45s` | the probe timed out |
| the last line `ssh` printed | `ssh` failed and said why |
| `ssh exited N` | `ssh` failed and said nothing |

A host that answers *partially* is still reachable: the values it managed to
emit are shown and the rest are `-`.
