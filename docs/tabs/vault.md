# Vault

The per-group vaults — `group_vars/<group>/vault.yml`, beside whichever
inventory pb resolved.

| Column | What it shows |
|---|---|
| Group | The group the vault belongs to |
| State | `encrypted`, or a red `PLAINTEXT` if the file is not encrypted at all |
| Size | |
| Path | Relative to the repo root |

## Verbs

`v`
:   **View.** Decrypts through `ansible-vault view` into a pager. If it cannot
    decrypt, pb shows Ansible's reason.

`e`
:   **Edit.** `ansible-vault edit` in `$EDITOR`. pb leaves the TUI so the editor
    gets a real terminal, and reloads when you come back.

`n`
:   **New group vault.** Asks for a group name and creates
    `group_vars/<group>/vault.yml`, encrypted, with a comment in it. It refuses
    to overwrite a vault that already exists.

`k`
:   **Rekey all.** Rekeys every vault in one `ansible-vault rekey`, prompting
    for the new password in a normal terminal.

!!! warning "After a rekey, update `.vault_pass`"
    Nothing will run until the password file matches the new password.

## The password file

pb reads the vault password from the repo's `.vault_pass`, the same way Ansible
does. Keep it `0600` and gitignored — [Doctor](doctor.md) checks both, and the
status bar says `.vault_pass MISSING` in red when it is not there.

pb writes an encrypted file only by invoking `ansible-vault` itself. It never
stores or transmits your password.
