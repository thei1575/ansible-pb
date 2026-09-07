# Contributing to pb

Thanks for wanting to help. pb is a small tool with a narrow job, so the bar
for a change is mostly "does it make running Ansible from a terminal less
error-prone".

## Ground rules

* **pb never reimplements Ansible.** Everything that touches infrastructure
  shells out to `ansible-playbook`, `ansible-inventory` or `ansible-vault`,
  and the exact command is shown before it runs. A patch that parses Ansible
  semantics itself, or that runs something the user has not been shown, will
  not be merged.
* **Nothing runs on the UI thread.** Anything that shells out is slow enough to
  freeze Textual. Use a `@work(thread=True)` worker, as the existing code does.
* **Secrets stay hidden by default.** `ansible-inventory` decrypts vaults, so
  anything credential-shaped is masked until the user asks. If you add a new
  view over inventory data, run it through `meta.redact()`.
* **Read-only means read-only.** The Inventory, Status, Roles and Doctor tabs
  must not mutate a host or the repo. Only the Playbooks and Vault tabs write,
  and only through Ansible.

## Getting set up

pb uses [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/thei1575/ansible-pb
cd ansible-pb
uv sync
```

Run it against a real Ansible repo:

```bash
uv run pb ~/my-ansible-repo
```

Plain `pip` works too, if you prefer:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e . && pip install ruff pytest
```

## Before you open a pull request

```bash
uv run ruff check .
uv run pytest
```

CI runs both on Python 3.11, 3.12 and 3.13, and once on macOS. Ansible is not installed
in CI and the tests do not need it — anything that shells out is tested against
a fixture repo on disk, or not at all.

### Tests

`tests/conftest.py` builds a throwaway Ansible repo in `tmp_path` (an
`ansible.cfg`, a couple of playbooks, a role, an inventory and a vault). Use
the `repo` fixture rather than mocking `Path`. Tests must not need a network,
an SSH key, or an `ansible` binary.

## Commit messages

Write the subject line as what the change does for the user, in the
imperative — `Mask cert private keys in the inventory tab`, not
`fix(meta): redaction`. The existing history is the guide.

## Reporting a bug

Open an issue with the template. Include the pb version (`pb --version`), your
Python version, your OS, and what `ansible --version` prints. If a command
pb built was wrong, paste the command line from the right-hand pane — that is
usually the whole bug.

Please do **not** file security issues in public. See [SECURITY.md](SECURITY.md).
