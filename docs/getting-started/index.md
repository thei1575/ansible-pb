# Install

pb needs **Python 3.11+** and a POSIX terminal (macOS or Linux). It allocates a
pty so Ansible keeps its colour, which is why there is no Windows build.

It is not on PyPI yet, so install it from the repository.

=== "uv"

    ```bash
    uv tool install git+https://github.com/thei1575/ansible-pb
    ```

=== "pipx"

    ```bash
    pipx install git+https://github.com/thei1575/ansible-pb
    ```

=== "From a clone"

    ```bash
    git clone https://github.com/thei1575/ansible-pb
    cd ansible-pb
    uv tool install .
    ```

Check it landed:

```bash
pb --version
```

## Ansible is not a dependency

pb declares only [Textual](https://textual.textualize.io/) and PyYAML. It
drives whatever `ansible-playbook`, `ansible-inventory` and `ansible-vault` are
already on your `PATH`, so installing pb cannot disturb how you installed
Ansible — a distribution package, a pipx tool, a virtualenv, an
`ansible-core` pin, all fine.

The consequence is that pb needs Ansible to be *findable*. If `ansible
--version` works in the shell you start pb from, so does pb. The
[Doctor](../guide/doctor.md) tab checks this first.

## Add `.pb/` to your repo's `.gitignore`

pb records every run under `.pb/runs/` inside the Ansible repository, and those
records contain the complete Ansible output — which can include anything a task
printed.

```bash
echo '.pb/' >> ~/my-ansible-repo/.gitignore
```

!!! danger "Do this before your first apply"

    Run records are plain text and are not scrubbed. Committing them is how
    output that was only ever meant for your terminal ends up in the history of
    a shared repository. See [Files pb touches](../reference/files.md).

## Optional extras

Nothing below is required, but Doctor will mention each one.

| Tool | What it adds |
|---|---|
| `ansible-lint` | Doctor reports whether it is installed; pb itself does not invoke it |
| `ssh` | Required for the [Status](../guide/status.md) tab and for `s` in the Inventory tab |
| `git` | Required for the `●` uncommitted marker, the changes viewer, and the commit recorded with each run |
| `openssl` on the hosts | The Status probe reads Let's Encrypt certificate expiry with it |
| `docker` on the hosts | The Status probe lists running containers with it |

## Next

[First run :octicons-arrow-right-24:](first-run.md){ .md-button .md-button--primary }
[Repository layout :octicons-arrow-right-24:](repository-layout.md){ .md-button }
