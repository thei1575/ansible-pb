# History

<kbd>6</kbd>

Every run pb has made, newest first, with its full output kept. Infrastructure
work needs an answer to "what did I apply, when, against which commit, and did
it work" — the terminal scrollback is not that answer, and this is.

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>o</kbd> | Open the saved output |
| <kbd>a</kbd> | Run the same command again |

</div>

Recording is automatic and applies to every run pb launches: applies, dry runs,
syntax checks, and the ad-hoc `ping` and `setup` from the
[Inventory](inventory.md) tab. There is nothing to switch on.

## What is recorded

Each run produces two files under `.pb/runs/`, named by local timestamp:

```
.pb/runs/20260907-142233.json
.pb/runs/20260907-142233.log
```

The JSON sidecar holds:

| Field | What |
|---|---|
| `label` | e.g. `webservers (apply)`, `ping web01` |
| `argv` | the exact command, as a list — what <kbd>a</kbd> replays |
| `started`, `duration` | Unix timestamp and elapsed seconds |
| `exit_code` | Ansible's, verbatim |
| `recap` | the `PLAY RECAP` counters, per host |
| `git_sha`, `git_branch`, `git_dirty` | the short commit, the branch, and how many files differed from `HEAD` |
| `hosts` | the hosts that appeared in the recap |

The `.log` file is the complete captured output with ANSI escapes stripped, so
it greps.

### The recap

pb parses the `PLAY RECAP` block into per-host counters —
`ok`, `changed`, `unreachable`, `failed`, `skipped`, `rescued`, `ignored` — and
the table shows the totals across hosts as e.g. `ok=41 changed=3`. Only
non-zero counters are shown, so a clean run reads short.

### `applied`

A record knows whether it was a *real* apply: a run counts as applied unless its
command contained `--check`, `--syntax-check` or `--list-hosts`. That is what
makes <kbd>a</kbd> ask for confirmation on some records and not others.

## Re-running

<kbd>a</kbd> replays the recorded `argv` exactly — same tags, same limit, same
extra arguments, whatever your current options happen to be. It does **not**
rebuild the command from today's settings.

If the record applied changes the first time, pb confirms first and shows you
the command and a reminder that it did. If it was a dry run or a syntax check,
it just runs.

!!! warning "Same command, possibly different result"

    The command is replayed as recorded; the repository is not. If the playbook,
    the roles or the inventory changed since — or if you are on a different
    commit — the run does something different. The record names the commit it
    ran against, which is how you tell.

## Pruning, and what to do about it

pb keeps the **most recent 300** records and deletes the JSON and `.log` of
anything beyond that. It never removes the `.pb/runs/` directory itself, and a
failure to write a record never kills a run — losing history must not cost you
the output you are watching.

!!! danger "Add `.pb/` to your `.gitignore`"

    Run records contain the complete Ansible output, which can include anything
    a task printed. They are not scrubbed. See
    [Files pb touches](../reference/files.md).

If you want a run kept beyond the last 300, copy the pair out. <kbd>s</kbd> in
the run view also writes a standalone
`pb-<label>-<timestamp>.log` in the repository root, which is why the project's
own `.gitignore` covers `pb-*.log` as well as `.pb/`.

## Unreadable records are skipped

Loading the history reads every `*.json` in the directory and silently skips
anything it cannot parse — a truncated write, a file from an older schema. A
corrupt record costs you that row, not the tab.
