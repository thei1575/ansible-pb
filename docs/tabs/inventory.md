# Inventory

Hosts, groups and resolved variables, straight from `ansible-inventory`. This
is the same data Ansible will use, not pb's own parse of your YAML.

| Column | What it shows |
|---|---|
| Host | The inventory hostname |
| Address | `ansible_host`, where set |
| Groups | Every group the host belongs to |

The detail pane lists the host's groups and its interesting variables —
`ansible_*` internals are dropped apart from `ansible_host` and `ansible_user`.

## Verbs

`p`
:   **Ping.** `ansible <host> -m ping`.

`f`
:   **Gather facts.** `ansible <host> -m setup`.

`i`
:   **Resolved vars.** Every variable, as JSON, in a pager.

`s`
:   **SSH.** Opens a session as `ansible_user` (or `root`) at the host's
    address. pb leaves the TUI and returns when you exit the shell.

`R`
:   **Reveal secrets.** Toggles the mask. pb warns you while they are on
    screen.

## Secrets are masked by default

`ansible-inventory` decrypts the vaults to resolve variables, so the plaintext
of every group vault passes through pb. Anything whose name looks like a
credential — `*_password`, `*_token`, `*_key`, `secret`, `salt`, … — is masked
until you press `R`, in both the detail pane and the JSON view.

!!! warning "The mask is a courtesy, not a boundary"
    It guards against shoulder-surfing and screen-sharing. Do not screen-share
    the Inventory tab with values revealed. See [Security](../security.md).

## When there are no hosts

pb shows why rather than showing you an empty table. `ansible-inventory` warns
on stderr, so a warning about your inventory plugin is kept and displayed
alongside the parsed result — "no hosts" says what went wrong instead of
looking like a pb bug. [Doctor](doctor.md) repeats it, with the inventory path
and where that path came from.
