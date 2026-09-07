# Doctor

A preflight over the whole repository. It runs when you first open the tab, and
`r` re-runs it. Every check is `ok`, `warn` or `fail`, with the detail that
explains it.

| Check | Passes when |
|---|---|
| `ansible` | `ansible --version` runs, and its first line is shown |
| inventory path | The resolved path exists — and the detail names where the path came from: `--inventory`, `ANSIBLE_INVENTORY`, `ansible.cfg`, found, or the default |
| `group_vars` | A `group_vars` directory sits beside the inventory (a warning if not) |
| vault password | `.vault_pass` exists and is `0600` |
| collections | `collections/ansible_collections/` has something in it, listed by name |
| `vault <group>` | Each vault is encrypted and `ansible-vault view` decrypts it |
| inventory | `ansible-inventory` parsed, with the host and group counts — or the error or warning it printed |
| `syntax <playbook>` | Every playbook passes `--syntax-check`, with Ansible's own message when it does not |
| `ansible-lint` | Installed. Optional, so a miss is a warning |

Because the inventory row names both the path and where that path came from, it
is the quickest way to check that pb and Ansible are looking at the same
inventory — see [Your repository](../repository.md).

Doctor only reads. It runs `--syntax-check` and `ansible-vault view`, and
touches no host.
