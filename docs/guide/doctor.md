# Doctor

<kbd>7</kbd>

A preflight over the whole repository. This is the tab to open first in a repo
pb has not seen, and the tab to open when something behaves oddly.

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>r</kbd> | Re-run every check |

</div>

Doctor runs once, automatically, the first time you open the tab. Each check
reports `✔ ok`, `• warn` or `✘ fail`, with the detail that produced it.

## The checks, in order

### `ansible`

Runs `ansible --version` and shows its first line. Fails if there is no
`ansible` on `PATH` — in which case nothing else in pb will work either, since
[pb never reimplements Ansible](../project/architecture.md#pb-never-reimplements-ansible).

### `inventory path`

**The most useful line in pb.** It names the inventory pb settled on, where that
came from, and whether it exists:

```
inventory path   ✔ ok     inventories/production (from ansible.cfg)
inventory path   ✘ fail   inventories/staging (from -i) — does not exist
```

The origin is one of `from -i`, `from $ANSIBLE_INVENTORY`, `from ansible.cfg`,
`found in the repo`, or `pb's default — nothing named one`. It is the quickest
way to check that pb and Ansible agree about your repository, and every other
tab is derived from it.

A path that `-i`, the environment or `ansible.cfg` names is honoured **even if
it does not exist**, so a misconfiguration is reported here rather than papered
over. See [Inventory resolution](../reference/inventory-resolution.md).

### `group_vars`

Whether a `group_vars/` directory exists beside whichever inventory won. A
**warning**, not a failure — plenty of repositories keep their variables
elsewhere, but if you expected the [Vault](vault.md) tab to have rows and it
does not, this is why.

### `vault password`

Two things about `<repo>/.vault_pass`:

- missing → **fail**, `is missing — nothing will run`
- present but not mode `0600` → **fail**, `should be 0o600`
- present and `0600` → **ok**

### `collections`

Lists what is installed under `collections/ansible_collections/`, as
`namespace.name`. Fails when the directory is absent or empty, with the hint
`run: make deps` — pb does not install collections for you.

### `vault <group>`

One check per vault the [Vault](vault.md) tab found:

- not encrypted → **fail**, `<path> is NOT encrypted`
- otherwise `ansible-vault view` is run against it: **ok** with
  `decrypts cleanly`, or **fail** with Ansible's own error, truncated

This is the check that catches a wrong or stale `.vault_pass` after a rekey.

### `inventory`

The result of the `ansible-inventory --list` that the
[Inventory](inventory.md) tab uses:

- Ansible errored → **fail** with its message
- Ansible warned → **warn** with the warning, and the hosts pb did find are
  still listed in the Inventory tab
- otherwise → `N hosts in M groups`, failing if `N` is zero

### `syntax <playbook>`

`ansible-playbook <file> --syntax-check` for **every** playbook in
`playbooks/`, with pb's `-i` where it applies. `clean`, or the tail of
Ansible's error.

This is why Doctor takes a moment on a large repository: it is a real
syntax check per playbook, not a YAML parse.

### `ansible-lint`

Whether `ansible-lint` is installed. **ok** if it is, **warn** with
`not installed (optional)` if not. pb does not invoke it — this is
informational.

## Reading it

The checks are ordered so that a failure high up explains the failures below it.
Work down from the top: a missing `ansible` fails everything, a wrong inventory
path fails the inventory and the vaults, and a stale `.vault_pass` fails every
vault and the inventory both.

If Doctor is clean and something still misbehaves, see
[Troubleshooting](../reference/troubleshooting.md).

!!! note "Doctor is read-only"

    Every check is an observation. Nothing here changes your repository, your
    vaults or your hosts — `ansible-playbook` is only ever invoked with
    `--syntax-check`, and `ansible-vault` only with `view`.
