# Playbooks

Everything in `playbooks/*.yml`, with what each one targets, which roles it
composes, and the exact command your current options produce.

| Column | What it shows |
|---|---|
| Playbook | The file name. A yellow `●` means it differs from `HEAD` |
| Kind | `aggregate` (imports other playbooks), `interactive` (prompts), or plain |
| Targets | The hosts and groups the plays name, with the group's members |
| Roles | How many roles the playbook composes |
| What it does | The playbook's own comment or `name` |

## The three verbs

`r`
:   **Apply.** Asks first, and the confirmation is not a yes/no on a pattern —
    see below.

`c` or `enter`
:   **Dry run.** `--check --diff`. `--diff` is implied even if the toggle is
    off, because a check run without it tells you almost nothing.

`s`
:   **Syntax check.** `--syntax-check`, no hosts touched.

`o` shows the playbook source.

## Apply names the blast radius

Before an apply, pb resolves the real host list through Ansible's
`--list-hosts` and shows you:

* the exact command it is about to run
* every host it would touch, with its address
* the tags and limit in force, if any
* how many uncommitted changes are in the repo

A pattern like `webservers:&production` is not an answer to "what am I about to
change". The resolved list is.

A playbook that prompts for input (`vars_prompt`) is marked `interactive` and
runs in the foreground — pb drops out of the TUI so you have a real terminal,
and returns when it finishes.

## Options

The options bar applies to whichever verb you use next, and the right-hand pane
re-renders the command as you change them.

| Key | Option | Becomes |
|---|---|---|
| `t` | Tags | `--tags a,b` — read from the playbook via Ansible, then picked from a list |
| `l` | Limit | `--limit x` — picked from the real groups and hosts in your inventory |
| `d` | Diff | `--diff` toggle |
| `v` | Verbosity | `-v` … `-vvvv`, cycling back to off |
| `e` | Extra args | Anything else, shell-quoted — `-e key=value --step` |
| `x` | Clear | Back to no options |

## While a run is on screen

The run view streams Ansible's output through a pty, so colour, progress and
`--step` prompts all behave as they do in a normal terminal.

| Key | Does |
|---|---|
| `ctrl+c` | Cancel the run |
| `w` | Toggle wrapping |
| `s` | Save the log |
| `g` / `G` | Top / bottom |
| `esc` | Close (once it has finished) |

Every run — applied or not — is recorded in [History](history.md) when it ends.
`q` refuses to quit pb while a run is still going.
