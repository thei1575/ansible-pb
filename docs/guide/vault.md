# Vault

<kbd>5</kbd>

One row per group vault, with whether it is actually encrypted and how big it
is. Every write goes through `ansible-vault` itself — pb never produces an
encrypted file another way.

<div class="pb-keys" markdown>

| Key | Does | Runs |
|---|---|---|
| <kbd>v</kbd> | View decrypted | `ansible-vault view <path>` |
| <kbd>e</kbd> | Edit in `$EDITOR` | `ansible-vault edit <path>` |
| <kbd>n</kbd> | New group vault | `ansible-vault encrypt` into a new path |
| <kbd>k</kbd> | Rekey every vault | `ansible-vault rekey <every path>` |

</div>

## What counts as a vault

pb lists `group_vars/*/vault.yml`, relative to whichever inventory won — so a
group is a directory:

```
inventories/production/group_vars/
  all/
    main.yml
    vault.yml     ← listed as "all"
  webservers/
    vault.yml     ← listed as "webservers"
```

A group written as a single `group_vars/webservers.yml` file has nowhere to put
a separate `vault.yml`, so it does not appear here. Ansible reads it either way;
this tab is a view over the directory-per-group convention.

The **Encrypted** column is not a guess: pb reads the first line of the file and
checks it starts with `$ANSIBLE_VAULT`. A `vault.yml` that was committed in
plaintext is shown as not encrypted here, and [Doctor](doctor.md) fails it
outright.

## Viewing

<kbd>v</kbd> shells out to `ansible-vault view` and shows the plaintext in a
highlighted viewer. If it cannot decrypt, pb shows Ansible's own error rather
than an empty pane — usually a `.vault_pass` that is missing or wrong.

Doctor runs the same `view` against every vault as part of its preflight, so
"do all my vaults still decrypt" is one keypress in the Doctor tab.

## Editing

<kbd>e</kbd> drops out of the TUI into a normal terminal and runs
`ansible-vault edit`, which opens your `$EDITOR` on the decrypted contents and
re-encrypts on save. pb returns when the editor exits and reloads the
repository.

This has to leave the TUI: your editor wants a real terminal, and Ansible
handles the decrypt/re-encrypt round trip itself. pb never sees an intermediate
plaintext file.

## Creating

<kbd>n</kbd> asks for a group name and creates
`<group_vars>/<group>/vault.yml`, encrypted, containing a comment header:

```yaml
---
# Secrets for the <group> group.
```

If the group already has a vault, pb says so and does nothing. The group
directory is created if it does not exist. Behind the scenes pb writes a
temporary plaintext file in the repository root, encrypts it to the target path
with `ansible-vault encrypt --output`, and removes the temporary file — whether
or not the encryption succeeded.

## Rekeying

<kbd>k</kbd> rekeys **every** vault in one `ansible-vault rekey` invocation,
after a confirmation. It drops to a normal terminal, because Ansible prompts
for the new password there.

!!! danger "Update `.vault_pass` afterwards or nothing will run"

    Rekeying changes the password on the files; it does not change the password
    file pb and Ansible read. Until you update `.vault_pass`, every command that
    touches a vault fails — including the inventory load, which means most of
    pb. The confirmation says so, and this is the one operation worth doing with
    a clean working tree so you can `git checkout` out of a mistake.

## The password file

pb reads the vault password from `<repo>/.vault_pass`, the same way Ansible does
through your `ansible.cfg`. It never stores it, never transmits it, and never
prompts for it.

Doctor checks two things about it:

- that it exists — if not, the check **fails**, because nothing that touches a
  vault will run
- that its mode is exactly `0600` — anything else is a **fail** with
  `should be 0o600`

Keep it gitignored. See [Files pb touches](../reference/files.md).
