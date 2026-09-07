# Roles

<kbd>4</kbd>

Every directory under `roles/` becomes a row, with what it contains and which
playbooks use it. This is the read-only tab you use to answer "what does this
role actually do, and who calls it" without leaving pb.

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>t</kbd> | Task files — opens the file, or a picker when there are several |
| <kbd>d</kbd> | `defaults/main.yml` |

</div>

Both open a highlighted, scrollable viewer. <kbd>esc</kbd> or <kbd>q</kbd>
closes it.

## What each row shows

| Column | Comes from |
|---|---|
| Tasks | the number of `tasks/*.yml` files |
| Parts | which of `defaults`, `handlers`, `templates`, `files`, `vars`, `meta` exist |
| Used by | the playbooks whose `roles:` list names this role |

"Used by" is built from the playbook parsing, so a role invoked from a play's
`roles:` list is credited to that playbook — named once even if several plays in
it use the role.

!!! note "`include_role` and `import_role` are not counted"

    pb reads each playbook's `roles:` key. A role pulled in from *inside* a task
    file with `include_role` or `import_role`, or reached through a
    dependency in another role's `meta/main.yml`, shows an empty "Used by".
    It is still listed as a role — only the reverse index misses it.

    Following those would mean parsing task semantics, which is
    [something pb does not do](../project/architecture.md#pb-never-reimplements-ansible).

## The uncommitted marker

A yellow `●` beside a role name means at least one file under `roles/<name>/`
differs from `HEAD`, staged or not. <kbd>ctrl</kbd>+<kbd>g</kbd> opens the
working-tree diff for the whole repository.

This is the same marker the [Playbooks](playbooks.md) tab uses, and the same
count the apply confirmation warns you about.

## Roles pb does not read

pb looks only at `roles/` in the repository root. Roles installed elsewhere —
`~/.ansible/roles`, a `roles_path` in `ansible.cfg`, a collection under
`collections/ansible_collections/` — are not listed. They still *run*, because
Ansible resolves them: the Roles tab is a view over the roles you maintain in
this repo, not over everything a play can reach.

Collections that the repo vendors are reported by [Doctor](doctor.md), which
lists what is installed under `collections/ansible_collections/`.
