# Keys

`?` inside pb shows this map. Bindings are attached to the focused table, so
the footer only ever offers what the current tab can do.

## Global

| Key | Does |
|---|---|
| `1` … `7` | Jump to a tab |
| `ctrl+r` | Reload everything from disk |
| `ctrl+g` | Show the uncommitted changes in the repo |
| `ctrl+p` | Command palette |
| `?` | This help |
| `q` | Quit — refused while a run is still going |

A yellow `●` next to a playbook or role means its files differ from `HEAD`.

## Playbooks

| Key | Does |
|---|---|
| `r` | Apply — asks first, and names the hosts it would touch |
| `c` or `enter` | Dry run (`--check --diff`) |
| `s` | Syntax check |
| `o` | Show the playbook source |
| `t` | Tags |
| `l` | Limit |
| `d` | Toggle `--diff` |
| `v` | Verbosity, `-v` … `-vvvv` |
| `e` | Extra arguments |
| `x` | Clear all options |

## Inventory

| Key | Does |
|---|---|
| `p` | Ping the host |
| `f` | Gather facts |
| `i` | Resolved variables, as JSON |
| `s` | SSH into the host — leaves the TUI, returns on exit |
| `R` | Reveal secrets, and hide them again |

## Status

| Key | Does |
|---|---|
| `r` | Probe every host over SSH |
| `s` | SSH into the selected host |

## Roles

| Key | Does |
|---|---|
| `d` | Role defaults |
| `t` | Task files |

## Vault

| Key | Does |
|---|---|
| `v` | View decrypted |
| `e` | Edit in `$EDITOR` |
| `n` | New group vault |
| `k` | Rekey every vault |

## History

| Key | Does |
|---|---|
| `o` | Open the saved output |
| `a` | Run the same command again |

## Doctor

| Key | Does |
|---|---|
| `r` | Re-run the checks |

## While a run is on screen

| Key | Does |
|---|---|
| `ctrl+c` | Cancel the run |
| `w` | Toggle wrapping |
| `s` | Save the log |
| `g` / `G` | Top / bottom |
| `esc` | Close |
