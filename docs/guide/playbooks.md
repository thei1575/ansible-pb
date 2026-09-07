# Playbooks

<kbd>1</kbd>

Every `*.yml` in `playbooks/` becomes a row. Its description comes from the
file's header comment or the first play's `name`.

The run panel shows the complete `ansible-playbook` command built from the
current options, together with the resolved target hosts.

## How pb reads a playbook

pb parses each file once, for three things it can show you without asking
Ansible:

| Shown as | Comes from |
|---|---|
| `play` | a normal playbook |
| `aggregate` | it is nothing but `import_playbook` entries - `site.yml` and friends |
| `interactive` | any play has `vars_prompt`, so it needs a real terminal |
| Targets | the `hosts:` of every play, named once each |
| Roles | the `roles:` list of every play |

`site.yml` sorts first, then the aggregates, then everything else
alphabetically.

A yellow `●` beside the name means the file differs from `HEAD`.
<kbd>ctrl</kbd>+<kbd>g</kbd> shows the working-tree diff.

## The three ways to run

<div class="pb-keys" markdown>

| Key | Mode | Command pb builds |
|---|---|---|
| <kbd>r</kbd> | apply | `ansible-playbook <file>` - **asks first** |
| <kbd>c</kbd> | dry run | `ansible-playbook <file> --check --diff` |
| <kbd>s</kbd> | syntax check | `ansible-playbook <file> --syntax-check` |
| <kbd>enter</kbd> | dry run | same as <kbd>c</kbd> |
| <kbd>o</kbd> | - | show the playbook source, highlighted |

</div>

A `--check` without `--diff` tells you almost nothing, so pb adds `--diff` to a
dry run rather than making the toggle a prerequisite. If you have already turned
`--diff` on yourself, it is not added twice.

An **interactive** playbook - one with `vars_prompt` - cannot stream through
pb's pane, because a prompt would deadlock the reader. Applying one drops out
of the TUI into a normal terminal and returns when it exits.

## Options

The five knobs are shared by every playbook action and shown in the bar along
the bottom. Active ones are highlighted; <kbd>x</kbd> clears all of them.

<div class="pb-keys" markdown>

| Key | Option | Becomes |
|---|---|---|
| <kbd>t</kbd> | Tags | `--tags a,b,c` |
| <kbd>l</kbd> | Limit | `--limit <pattern>` |
| <kbd>d</kbd> | Diff toggle | `--diff` |
| <kbd>v</kbd> | Verbosity | `-v` … `-vvvv`, cycling back to off |
| <kbd>e</kbd> | Extra arguments | split with shell quoting and appended verbatim |
| <kbd>x</kbd> | - | clear all five |

</div>

### Tags come from Ansible

<kbd>t</kbd> asks Ansible for the real tag list - `--list-tags`, parsed out of
the `TASK TAGS:` line - so tags that a *role* adds are in the picker too.
Parsing the YAML would miss those.

The lookup runs in a worker thread the first time you open the picker for a
playbook and is remembered afterwards. <kbd>ctrl</kbd>+<kbd>r</kbd> forgets it
again. `never` is filtered out - it is Ansible's "only when asked for
explicitly", so offering it in a picker would be misleading.

In the picker: <kbd>space</kbd> toggles, <kbd>enter</kbd> accepts,
<kbd>ctrl</kbd>+<kbd>a</kbd> selects all, <kbd>ctrl</kbd>+<kbd>n</kbd> selects
none, and <kbd>esc</kbd> cancels without changing anything.

### Limit is a real list

<kbd>l</kbd> offers `all`, then every group in the inventory with its members,
then every host with its address. You are choosing from what the inventory
actually contains rather than typing a pattern and hoping.

### Extra arguments

<kbd>e</kbd> takes a free-text string, splits it with shell quoting, and appends
it. Anything `ansible-playbook` accepts works - `-e key=value`, `--step`,
`--start-at-task=…`, `--vault-id`.

!!! warning "Extra arguments are not validated"

    pb appends them verbatim. They are visible in the command pane, which is
    the point - read it before you run.

## Applying { #applying }

<kbd>r</kbd> never runs immediately. A pattern is not an answer to "what am I
about to change", so pb first asks Ansible for the resolved target hosts with
`--list-hosts`, honouring your current `--limit`, and then shows you:

```
Apply webservers.yml?

  This changes real infrastructure.

  ansible-playbook playbooks/webservers.yml --tags certs --limit web01 --diff

  would touch 1 host
    web01  10.0.4.11

  only tags: certs
  limited to: web01

  3 uncommitted change(s) in the repo - ctrl+g to see them

                                       [ Cancel ]  [ Apply ]
```

The addresses come from the resolved inventory, so a host whose `ansible_host`
does not match its inventory name shows both. If the host list could not be
resolved at all, pb says so in red rather than pretending the count is zero.

The uncommitted-changes line is a deliberate nag: applying a repository that
differs from `HEAD` means the run cannot be reproduced from a commit.

## While a run is on screen

The run opens full-screen and streams Ansible's output line by line, in colour
- pb gives the child a pty rather than a pipe, because Ansible only emits
colour when it believes it is talking to a terminal.

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>ctrl</kbd>+<kbd>c</kbd> | Cancel - terminates the child's whole process group, not just Ansible |
| <kbd>w</kbd> | Toggle line wrapping |
| <kbd>s</kbd> | Save the log |
| <kbd>g</kbd> / <kbd>G</kbd> | Top / bottom |
| <kbd>esc</kbd> or <kbd>q</kbd> | Close |

</div>

Cancelling still lets the dying child flush its last lines, so you keep whatever
it managed to print. On close, pb reloads the repository - a finished run is new
[history](history.md), and an apply may have changed the working tree.

!!! info "pb will not quit mid-apply"

    <kbd>q</kbd> is refused while a run that changes something is still going.
    Cancel it or let it finish.

## Recorded automatically

Every run - apply, dry run or syntax check - is written to `.pb/runs/` with the
command, tags, exit code, per-host recap, the commit it ran against and the full
output. Nothing to remember to switch on. See [History](history.md).
