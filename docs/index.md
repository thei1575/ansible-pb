---
hide:
  - navigation
  - toc
---

<div class="pb-hero" markdown>

<span class="pb-kicker">PB / RUN CONTROL</span>

# Ansible operations, from inventory to run record.

pb gives an Ansible repository a working surface for day-to-day operations.
Inspect the resolved state, set the scope, review the command, run it, and keep
the result with the repository.

[Install pb](getting-started/index.md){ .md-button .md-button--primary }
[Read the operator guide](getting-started/first-run.md){ .md-button }

</div>

<div class="pb-console-label"><span>SESSION</span><code>production / webservers.yml</code><span>READY</span></div>

<div class="pb-term" markdown>
<div class="pb-term-bar"><strong>pb</strong><em>Playbooks</em><span>inventory loaded</span></div>

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
 tags certs  limit web01  diff on  -v 0
 r Run  c Dry run  s Syntax  t Tags  l Limit  d Diff  ? Help  q Quit
```

</div>

## One run, fully accounted for

The interface follows the same sequence an operator follows at the shell. Each
stage has a visible input and a recorded result.

<div class="pb-runbook" markdown>

1. **Inspect**

    Read playbooks, roles, inventory, host variables, and repository checks from
    the current checkout.

2. **Scope**

    Choose tags and hosts from values returned by Ansible. pb resolves the final
    target list before an apply.

3. **Review**

    Check the complete command, addresses, and working-tree state in the run
    panel.

4. **Execute**

    Apply, run check mode, or validate syntax in a pty with Ansible's colour and
    streaming output intact.

5. **Record**

    Keep the command, output, exit code, recap, timestamp, and Git commit under
    `.pb/runs/`.

</div>

## Plugin system

The plugin API is a core pb surface for repository-specific operations. Plugins
run inside the application and use the same repository, inventory, history,
launch, notification, and viewer interfaces as built-in features.

| Extension point | Purpose |
|---|---|
| Tabs and key actions | Add an operational screen or extend an existing one |
| Command palette | Expose plugin commands through the global palette |
| Doctor checks | Validate tools, configuration, and repository requirements |
| Run hooks | Inspect, change, stop, or respond to a command |
| Detail panes and status bar | Add context to existing pb surfaces |

[Manage plugins](guide/plugins.md){ .md-button .md-button--primary }
[Build a plugin](plugins/quickstart.md){ .md-button }
[Plugin API](reference/writing-plugins.md){ .md-button }

## Repository workspace

| Surface | Operational use |
|---|---|
| [Playbooks](guide/playbooks.md) | Build and run `ansible-playbook` commands with tags, limits, diff, verbosity, and extra arguments |
| [Inventory](guide/inventory.md) | Inspect hosts, groups, and resolved variables; run ping and facts; open SSH sessions |
| [Status](guide/status.md) | Read uptime, disk, memory, failed units, containers, package updates, and certificate expiry over SSH |
| [Roles](guide/roles.md) | Read task files and defaults, then trace direct playbook use |
| [Vault](guide/vault.md) | View, edit, create, and rekey group vaults through `ansible-vault` |
| [History](guide/history.md) | Review saved run output and repeat an exact command |
| [Doctor](guide/doctor.md) | Check inventory selection, tools, collections, vaults, and playbook syntax |
| [Plugins](guide/plugins.md) | Install, update, enable, disable, and inspect pb extensions |

## Ansible remains the execution layer

pb invokes `ansible-playbook`, `ansible-inventory`, `ansible-vault`, and
`ansible` from `PATH`. This keeps repository configuration, inventory plugins,
vault handling, and installed collections in Ansible's control. The exact
command appears in the interface before execution.

```bash
cd ~/my-ansible-repo
pb
```

The nearest `ansible.cfg` establishes the repository root. Use `-i` to select a
different inventory for the session.

## System requirements

- Python 3.11 or newer
- macOS or Linux with a POSIX terminal
- Ansible available on `PATH`
- An Ansible repository containing `ansible.cfg`

!!! warning "Run records may contain secrets"

    `.pb/runs/` stores complete Ansible output. Add `.pb/` to the repository's
    `.gitignore` and manage its local permissions accordingly. Review the
    [security model](project/security.md) before using pb with production hosts.
