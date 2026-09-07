---
hide:
  - navigation
---

<div class="pb-hero" markdown>

# pb

A terminal console for an Ansible repository. Run playbooks, read the resolved
inventory, probe hosts over SSH, manage per-group vaults, and keep a record of
everything you applied — without leaving the terminal.

[Install pb](getting-started/index.md){ .md-button .md-button--primary }
[Take the first run](getting-started/first-run.md){ .md-button }

</div>

pb does not reimplement Ansible. It shells out to `ansible-playbook`,
`ansible-inventory` and `ansible-vault`, and always shows you the exact command
before it runs.

```bash
cd ~/my-ansible-repo && pb
```

<div class="pb-term" markdown>
<div class="pb-term-bar"><span></span><span></span><span></span><em>pb — Playbooks</em></div>

```{ .text .no-copy }
 Playbooks  Inventory  Status  Roles  Vault  History  Doctor  Plugins
┌──────────────────────────────────────────┬─────────────────────────────────┐
│ ● site.yml        Everything, in order   │ COMMAND                         │
│   webservers.yml  nginx and certificates │ ansible-playbook                │
│   database.yml    postgres and backups   │     playbooks/webservers.yml    │
│   bootstrap.yml   A fresh host, once     │     --tags certs --limit web01  │
│                                          │     --diff                      │
│                                          │                                 │
│                                          │ HOSTS                           │
│                                          │ web01  10.0.4.11                │
└──────────────────────────────────────────┴─────────────────────────────────┘
 tags certs  limit web01  diff on  -v 0  extra —   t·l·d·v·e edit  x clear
 r Run  c Dry run  s Syntax  t Tags  l Limit  d Diff  ? Help  q Quit
```

</div>

## What pb gives you

<div class="grid cards" markdown>

-   :material-play-box-outline:{ .lg .middle } **Run anything, deliberately**

    ---

    Apply, dry-run or syntax-check any playbook, with `--tags` and `--limit`
    pickers fed by Ansible's own answers. The pane on the right shows the exact
    command your options produce.

    [:octicons-arrow-right-24: Playbooks](guide/playbooks.md)

-   :material-target:{ .lg .middle } **See the blast radius first**

    ---

    Applying resolves the real host list through `--list-hosts` and names the
    hosts and their addresses before you confirm — not the pattern you typed.

    [:octicons-arrow-right-24: Applying a playbook](guide/playbooks.md#applying)

-   :material-file-tree:{ .lg .middle } **Read the resolved inventory**

    ---

    Hosts, groups and fully resolved variables straight from
    `ansible-inventory`, with credential-shaped values masked until you ask.
    Ping, gather facts, or drop into an SSH session.

    [:octicons-arrow-right-24: Inventory](guide/inventory.md)

-   :material-heart-pulse:{ .lg .middle } **Check the fleet, read-only**

    ---

    One SSH round trip per host: uptime, load, disk, memory, pending updates,
    failed units, running containers and certificate expiry. Nothing is
    changed.

    [:octicons-arrow-right-24: Status](guide/status.md)

-   :material-history:{ .lg .middle } **Keep the record**

    ---

    Every run is written to `.pb/runs/` — command, tags, exit code, recap, the
    commit it ran against, and the full output. "What did I apply, and did it
    work" has an answer.

    [:octicons-arrow-right-24: History](guide/history.md)

-   :material-lock-outline:{ .lg .middle } **Handle the vaults**

    ---

    View, edit, create and rekey the per-group vaults, always through
    `ansible-vault` itself. pb never writes an encrypted file another way.

    [:octicons-arrow-right-24: Vault](guide/vault.md)

-   :material-puzzle-outline:{ .lg .middle } **Extend it, without forking it**

    ---

    pb is deliberately narrow. A plugin is a git repository pb clones and
    imports at start-up: a tab of your own, extra keys, extra Doctor checks, or
    a veto on a command before it runs. A broken one costs you that plugin,
    never your console.

    [:octicons-arrow-right-24: Plugins](guide/plugins.md)

</div>

## What it does that a Makefile cannot

!!! abstract "Three things worth the tab"

    **It shows the blast radius.** Applying resolves the real host list through
    `--list-hosts` and names the hosts and addresses before you confirm, rather
    than showing you a pattern.

    **It keeps a record.** Every run is written to `.pb/runs/` in the repo —
    command, tags, exit code, recap, the commit it ran against, and the full
    output.

    **It marks uncommitted work.** A yellow `●` on a playbook or role means its
    files differ from `HEAD`; <kbd>ctrl</kbd>+<kbd>g</kbd> shows the diff.

## The eight tabs

| Tab | What it is for |
|---|---|
| [Playbooks](guide/playbooks.md) | Run, dry-run or syntax-check anything, with `--tags`/`--limit` pickers |
| [Inventory](guide/inventory.md) | Hosts, groups, resolved vars, ping, facts, ssh |
| [Status](guide/status.md) | Live health per host over SSH: uptime, disk, failed units, containers, cert expiry |
| [Roles](guide/roles.md) | Task files, defaults, and which playbooks use each role |
| [Vault](guide/vault.md) | View, edit, create and rekey the per-group vaults |
| [History](guide/history.md) | Every run pb has made, with its output kept |
| [Doctor](guide/doctor.md) | Preflight over the whole repo |
| [Plugins](guide/plugins.md) | Install, update and inspect the plugins that extend pb |

## Requirements

- Python 3.11 or newer
- A POSIX terminal — macOS or Linux. pb allocates a pty so Ansible keeps its
  colour, which Windows has no equivalent for.
- An `ansible` on your `PATH`. Ansible is deliberately **not** a dependency of
  pb: it drives whatever you already have, so it never interferes with how you
  install it.
- An Ansible repository with an `ansible.cfg` at its root.

!!! warning "pb runs Ansible as you"

    pb has as much reach as your own shell does, and `ansible-inventory`
    decrypts your vaults to resolve variables. Read
    [Security](project/security.md) before you point it at production.
