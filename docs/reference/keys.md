# Key map

The <kbd>?</kbd> key opens this map inside pb. The footer lists actions for the
focused tab, so the same letter may perform a different local action elsewhere.

## Global

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>1</kbd> … <kbd>8</kbd> | Jump to a tab |
| <kbd>?</kbd> | This help, inside pb |
| <kbd>ctrl</kbd>+<kbd>r</kbd> | Reload everything from disk |
| <kbd>ctrl</kbd>+<kbd>g</kbd> | The working-tree diff - `git status` plus the diff |
| <kbd>ctrl</kbd>+<kbd>u</kbd> | Check for a newer pb - see [Updating](updates.md) |
| <kbd>ctrl</kbd>+<kbd>p</kbd> | Command palette; [plugins](../guide/plugins.md) can add commands |
| <kbd>q</kbd> | Quit - refused while a run that changes something is going |

</div>

A yellow `●` next to a playbook or role means its files differ from `HEAD`.

## Playbooks &nbsp;<kbd>1</kbd>

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>r</kbd> | Apply after confirmation with the resolved target hosts |
| <kbd>c</kbd> | Dry run - `--check --diff` |
| <kbd>enter</kbd> | Dry run |
| <kbd>s</kbd> | Syntax check |
| <kbd>o</kbd> | Show the playbook source |
| <kbd>t</kbd> | Tags picker |
| <kbd>l</kbd> | Limit picker |
| <kbd>d</kbd> | `--diff` toggle |
| <kbd>v</kbd> | Verbosity - cycles `-v` … `-vvvv`, then off |
| <kbd>e</kbd> | Extra `ansible-playbook` arguments |
| <kbd>x</kbd> | Clear all options |

</div>

The pane on the right shows the exact command your options produce.

## Inventory &nbsp;<kbd>2</kbd>

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>p</kbd> | Ping - `ansible <host> -m ping` |
| <kbd>f</kbd> | Gather facts - `ansible <host> -m setup` |
| <kbd>i</kbd> | Resolved vars, as JSON |
| <kbd>s</kbd> | SSH into the host - leaves the TUI, returns on exit |
| <kbd>R</kbd> | Reveal secrets, and hide them again |

</div>

`ansible-inventory` decrypts the vaults, so anything that looks like a
credential is masked until you ask. See
[Inventory](../guide/inventory.md#secrets-are-masked-by-default).

## Status &nbsp;<kbd>3</kbd>

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>r</kbd> | Probe every host over SSH - read-only |
| <kbd>s</kbd> | SSH into the selected host |

</div>

## Roles &nbsp;<kbd>4</kbd>

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>d</kbd> | Role defaults - `defaults/main.yml` |
| <kbd>t</kbd> | Task files |

</div>

## Vault &nbsp;<kbd>5</kbd>

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>v</kbd> | View decrypted |
| <kbd>e</kbd> | Edit in `$EDITOR` |
| <kbd>n</kbd> | New group vault |
| <kbd>k</kbd> | Rekey every vault |

</div>

## History &nbsp;<kbd>6</kbd>

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>o</kbd> | Open the saved output |
| <kbd>a</kbd> | Run the same command again |

</div>

## Doctor &nbsp;<kbd>7</kbd>

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>r</kbd> | Re-run the checks |

</div>

## Plugins &nbsp;<kbd>8</kbd>

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>i</kbd> | Install one from GitHub - asks before it clones |
| <kbd>u</kbd> | Update the selected plugin |
| <kbd>e</kbd> | Enable or disable it |
| <kbd>r</kbd> | Remove it |
| <kbd>o</kbd> | Everything pb knows about it, including a load failure |

</div>

Installing, enabling and removing take effect the next time pb starts. See
[Plugins](../guide/plugins.md).

A plugin can bind keys of its own, on its own tab or on one of the tabs above,
and can replace what a key already listed here does. The footer is built from
whatever is actually bound, so it stays the truth - and `pb --no-plugins`
gives you exactly the map on this page.

## While a run is on screen

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>ctrl</kbd>+<kbd>c</kbd> | Cancel - terminates the child's whole process group |
| <kbd>w</kbd> | Toggle wrapping |
| <kbd>s</kbd> | Save the log to `pb-<label>-<timestamp>.log` |
| <kbd>g</kbd> / <kbd>G</kbd> | Top / bottom |
| <kbd>esc</kbd> or <kbd>q</kbd> | Close - refused while still running |

</div>

## In a picker or prompt

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>space</kbd> | Toggle the highlighted item (multi-select) |
| <kbd>enter</kbd> | Accept |
| <kbd>ctrl</kbd>+<kbd>a</kbd> | Select all (multi-select) |
| <kbd>ctrl</kbd>+<kbd>n</kbd> | Select none (multi-select) |
| <kbd>esc</kbd> | Cancel, changing nothing |

</div>

## In a viewer

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>esc</kbd> or <kbd>q</kbd> | Close |
| arrows, <kbd>page up</kbd>/<kbd>down</kbd>, <kbd>home</kbd>/<kbd>end</kbd> | Scroll |

</div>
