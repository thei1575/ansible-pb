# History

Every run pb has made, newest first, kept in `.pb/runs/` in the repo and
pruned to the last 300. The log scrolls away; this does not.

| Column | What it shows |
|---|---|
| When | Local time the run started |
| What | The label — the playbook and the mode. Bold for a real apply |
| Result | `✔ ok`, or `✘` and the exit code |
| Took | Wall-clock seconds |
| Recap | Totals from Ansible's PLAY RECAP — `ok=`, `changed=`, `failed=`, `unreachable=` |

The detail pane adds the whole story of the run: the exact argv, whether it
applied or was a check, the commit and branch it ran against and how many files
were uncommitted at the time, and the recap broken out per host.

`o` opens the full captured output. `a` runs the same command again — and asks
first if it applied changes the first time.

## What is recorded

Per run, as a JSON sidecar plus the captured output:

* the label and the full argv
* start time, duration and exit code
* the parsed PLAY RECAP, per host
* the git SHA, the branch, and the number of uncommitted files
* the hosts it targeted

Recording never breaks a run: if pb cannot write the record, the run still
happens.

!!! warning "Run records contain full Ansible output"
    Anything a task printed is in there. Add `.pb/` to your repo's
    `.gitignore`. pb prunes to the last 300 records and never deletes the
    directory itself.
