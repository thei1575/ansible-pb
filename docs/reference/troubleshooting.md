# Troubleshooting

Open [Doctor](../guide/doctor.md) with <kbd>7</kbd> before working through this
reference. Its check details identify most configuration and dependency errors.

## pb will not start

### `no ansible.cfg in … or any parent directory`

pb needs to know where the repository starts, and `ansible.cfg` is what marks
it. `cd` into the repo, or pass the path:

```bash
pb ~/my-ansible-repo
```

If your repository genuinely has no `ansible.cfg`, an empty one is enough:

```bash
touch ~/my-ansible-repo/ansible.cfg
```

### `<path> is not a directory`

The `path` argument is a *directory* inside the repository, not a playbook or an
inventory file. To choose an inventory, use `-i`.

## The wrong inventory

### pb shows an inventory I did not expect

Read the `inventory path` line in Doctor. It names the path **and where it came
from**. The usual causes, in order of likelihood:

1. `$ANSIBLE_INVENTORY` is exported in this shell. It beats `ansible.cfg`.
2. `ansible.cfg` has an `[defaults] inventory` you had forgotten.
3. Nothing names one, and pb picked by looking around - the line says
   `found in the repo`.

Override for a session with `pb -i <path>`. The full rules are in
[Inventory resolution](inventory-resolution.md).

### pb and Ansible disagree

Both should read the same thing. If they do not, compare environments:

```bash
env | grep ^ANSIBLE
```

`ANSIBLE_CONFIG` pointing somewhere unexpected is the other common cause - pb
reads `[defaults] inventory` from the repo's own `ansible.cfg`, while Ansible
honours `ANSIBLE_CONFIG` first. pb still passes no `-i` in that case, so
Ansible's answer is the one that runs; the disagreement is only in what pb
*shows*.

### A multi-source inventory only shows one source

By design. pb shows one inventory and derives `group_vars` from it, so it works
off the first source of a comma-separated list - and passes no `-i`, which is
what keeps Ansible seeing the whole list. See
[when pb passes `-i`](inventory-resolution.md#when-pb-passes-i).

## Empty tabs

### "no hosts" in the Inventory tab

Look at the `inventory` check in Doctor:

- **fail** with a message → Ansible could not read the inventory. The message is
  Ansible's own.
- **warn** with a message → Ansible warned. pb keeps the warning and shows it,
  and lists whatever hosts it did find. A single unparsable file in an inventory
  directory does this.
- **ok** with `0 hosts` → the inventory parsed and is empty. You are reading the
  wrong one.

### The Playbooks tab is empty

pb reads `playbooks/*.yml` and nothing else. Playbooks at the repository root,
under a different directory name, or with a `.yaml` extension are not listed.
`playbooks/` and `roles/` are the two names pb assumes.

### The Vault tab is empty

pb lists `<group_vars>/*/vault.yml`. Two things break that:

- `group_vars` is not beside the inventory pb settled on - Doctor warns
  `none beside the inventory`.
- Your groups are single files (`group_vars/webservers.yml`) rather than
  directories, so there is nowhere for a separate `vault.yml`. Ansible reads
  both layouts; this tab only shows the directory one.

### The Roles tab shows "Used by" as empty

pb builds that index from each playbook's `roles:` key. A role pulled in with
`include_role` or `import_role` from inside a task file, or via another role's
`meta/main.yml` dependencies, is not credited - following those means parsing
task semantics, which
[outside pb's execution boundary](../project/architecture.md#ansible-owns-execution-semantics).

## Vaults

### `could not decrypt` on view, or every vault fails in Doctor

Almost always `.vault_pass`: missing, wrong, or stale after a rekey. Doctor
checks its existence and mode; the `vault <group>` checks run a real
`ansible-vault view` and show Ansible's error.

If you have just rekeyed, update `.vault_pass` - until you do, the inventory
load fails too, which takes most of pb with it.

### `vault password … should be 0o600`

```bash
chmod 600 ~/my-ansible-repo/.vault_pass
```

### A vault shows as not encrypted

pb reads the first line and checks for the `$ANSIBLE_VAULT` header. A file that
fails this was committed in plaintext. Encrypt it:

```bash
ansible-vault encrypt inventories/production/group_vars/<group>/vault.yml
```

## Runs

### A run produced no output, or lost its `PLAY RECAP`

This was a real bug and is fixed. The parent used to close the pty slave as soon
as the child was spawned, so the master reported EOF the moment the child
exited - and on BSD that EOF discards whatever is still in the pty buffer, which
is where the last lines of a run live. A short command could lose everything it
printed.

If you see it on a current pb, open
[an issue](https://github.com/thei1575/ansible-pb/issues) with your OS and the
output of `ansible --version`.

### A run hangs with no output

Something in the run is prompting, and nothing in a pb run is interactive: a
prompt deadlocks the pty reader. Causes:

- a playbook with `vars_prompt` that pb did not detect - pb checks for the key
  and drops such playbooks to a real terminal, but only for **apply**, not for a
  dry run
- an SSH host key prompt, or a passphrase prompt for a key not in your agent
- `--ask-become-pass` or similar in your extra arguments

<kbd>ctrl</kbd>+<kbd>c</kbd> cancels and terminates the whole process group.
Then run it outside pb, or add the key to your agent.

### pb will not let me quit

<kbd>q</kbd> is refused while a run that changes something is still going -
Ansible is in its own process group, so quitting would leave it applying changes
with nothing left to show the output. Cancel with <kbd>ctrl</kbd>+<kbd>c</kbd>
or let it finish.

### Ansible has no colour

pb allocates a pty and sets `ANSIBLE_FORCE_COLOR=1`, `PY_COLORS=1` and
`TERM=xterm-256color`, so colour should survive. If it does not, check whether
your `ansible.cfg` sets `nocolor = 1` or your environment exports
`ANSIBLE_NOCOLOR`.

## Status

### Every host is unreachable

The probe uses `BatchMode=yes`, so it never prompts - a key that is not in your
agent looks exactly like a refused connection. Try one host by hand:

```bash
ssh -o BatchMode=yes <ansible_user>@<address> true
```

pb picks `<ansible_user>` from the host's `ansible_user` variable, `root`
otherwise, and `<address>` from `ansible_host`, the inventory name otherwise.

### Columns are `-` on some hosts

The probe emits `key=value` lines and omits anything unavailable, which keeps it
portable. A host without `systemd` has no failed-units or services count; a host
without `apt` has no update count; a host without `docker` has no containers. It
is still reachable, and its notes column is still meaningful.

### No certificate rows

The probe reads `/etc/letsencrypt/live/<fqdn>/cert.pem`, and it learns the
`<fqdn>`s from the host's own variables: every one whose name ends in `_fqdn`
with a non-empty string value. No such variable, no certificate row.

### `local connection - nothing to probe`

The host is `localhost`, or has `ansible_connection: local`. There is no SSH
round trip to make.

## Plugins

### A plugin is not there after I installed it

Installing, updating, enabling and removing all take effect the next time pb
starts - plugin code is imported once, at start-up. The
[Plugins](../guide/plugins.md) tab says `• pending restart` for exactly this
reason. Quit and start pb again.

### A plugin will not load

<kbd>8</kbd> then <kbd>o</kbd> shows the stage it failed at and the traceback.
From a shell, without starting the TUI:

```bash
pb plugin doctor
```

Three failures account for most of it: a `pb-plugin.toml` pb cannot use, a
module that raises on import, and a module that defines no `Plugin` subclass. A
plugin declaring an `api` number this pb does not speak is refused outright
rather than imported and failed halfway - `pb plugin doctor` prints the version
this pb speaks.

### Two plugins, and one of them never loads

They declare the same `module`. Plugins share `sys.path`, so one would shadow
the other; pb reports it instead of picking. One of them has to rename its
module - see [the manifest](writing-plugins.md#the-manifest).

### pb is misbehaving and a plugin might be why

Start without any of them:

```bash
pb --no-plugins        # PB_NO_PLUGINS=1 does the same
```

Nothing is uninstalled. If the problem goes away, re-enable them one at a time
with `pb plugin disable`/`enable`.

A plugin whose *hook* raises does not need this: pb catches it, switches that
plugin off for the rest of the session, removes its tabs, hands its replaced
actions back to the built-ins, and reports it as a failed
[Doctor](../guide/doctor.md) check. pb keeps running.

### A key does something I did not expect

A plugin can **replace** what one of pb's own keys does. The
[key map](keys.md) reflects whatever is actually bound, and the detail pane on
the Plugins tab lists the hooks each plugin implements. `pb --no-plugins`
gives you the built-in behaviour to compare against.

### `pb plugin update` threw away my edits

pb owns the directories under its config directory and resets them on update.
To work on a plugin, keep your own checkout and point pb at it - pb reads it in
place and never touches it with git:

```bash
pb plugin link ~/src/pb-mine
```

### `pb plugin install` refuses without asking

There is no terminal to ask in. Installing a plugin is a deliberate decision,
so pb refuses rather than installing silently. Pass `-y` if you have already
made it.

## Still stuck

Open an issue with the template. Include:

- `pb --version`
- your Python version and OS
- what `ansible --version` prints
- if a command pb built was wrong, **the command line from the right-hand
  pane** - that is usually the whole bug

Please report security issues privately instead. See
[Security](../project/security.md).
