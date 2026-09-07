# Roles

Every role in `roles/`, and — the part a directory listing cannot tell you —
which playbooks actually use it.

| Column | What it shows |
|---|---|
| Role | The role name. A yellow `●` means something under it differs from `HEAD` |
| Tasks | How many task files it has |
| Contains | Which of `defaults`, `handlers`, `templates`, `files`, `vars`, `meta` exist — `tasks only` when none do |
| Used by | The playbooks that reference it — red `unused` if none do |

`d` opens `defaults/main.yml`. `t` opens a task file, asking which one when
there is more than one.

`ctrl+g` shows the working-tree diff for everything uncommitted in the repo,
which is the fastest way to see what you are about to apply from a role you
have just edited.
