# Development

pb is a small tool with a narrow job, so the bar for a change is mostly "does
it make running Ansible from a terminal less error-prone".

## Getting set up

pb uses [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/thei1575/ansible-pb
cd ansible-pb
uv sync
uv run pb ~/my-ansible-repo
```

Plain `pip` works too:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e . && pip install ruff pytest
```

## Before you open a pull request

```bash
uv run ruff check .
uv run pytest
```

CI runs both on Python 3.11, 3.12 and 3.13, and once on macOS to keep the pty
handling honest. Ansible is not installed in CI and the tests do not need it:
`tests/conftest.py` builds a throwaway Ansible repo in `tmp_path` — an
`ansible.cfg`, a couple of playbooks, a role, an inventory and a vault — so
they need neither an `ansible` binary nor a network.

`Repo.discover` reads `$ANSIBLE_INVENTORY`, so an autouse fixture clears it: a
developer who has it exported must not get different results from CI.

## The invariants

These are what a patch has to hold. The
[contributing guide](https://github.com/thei1575/ansible-pb/blob/main/.github/CONTRIBUTING.md)
has the long version.

**pb never reimplements Ansible.** Everything that touches infrastructure
shells out to `ansible-playbook`, `ansible-inventory` or `ansible-vault`, and
the exact command is shown before it runs.

**Nothing runs on the UI thread.** Anything that shells out is slow enough to
freeze Textual. Use a `@work(thread=True)` worker, as the existing code does.

**Secrets stay hidden by default.** `ansible-inventory` decrypts vaults, so
anything credential-shaped is masked until the user asks. A new view over
inventory data goes through `meta.redact()`.

**Read-only means read-only.** The Inventory, Status, Roles and Doctor tabs
must not mutate a host or the repo. Only Playbooks and Vault write, and only
through Ansible.

## The code

```
src/pb/            the package — one module per concern
  app.py           the App, the tabs, and every key binding
  meta.py          read-only introspection of the Ansible repo
  runner.py        running ansible on a pty and streaming it back
  run.py           the full-screen run view
  history.py       the durable record under .pb/runs/
  hoststatus.py    the read-only SSH health probe
  widgets.py       the modal pickers, prompts and viewers
  pb.tcss          the stylesheet
tests/             pytest, against a fixture Ansible repo in tmp_path
docs/              this site
.github/           CI, the docs deploy, issue and pull-request templates,
                   and the contributing, security and conduct documents
```

## These docs

The site is [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).
To work on it:

```bash
uv run --group docs mkdocs serve
```

```bash
uv run --group docs mkdocs build --strict
```

`--strict` is what CI runs, so a broken link or a page missing from the nav
fails the build. The changelog and the security policy are not written twice:
those pages pull in `CHANGELOG.md` and `.github/SECURITY.md` from the
repository root with a snippet.

Pushing to `main` publishes the site to GitHub Pages; pull requests build it
without publishing.

## Commit messages

Write the subject line as what the change does for the user, in the
imperative — `Mask cert private keys in the inventory tab`, not
`fix(meta): redaction`. The existing history is the guide.

## Reporting a bug

Open an issue with the template, and include the pb version (`pb --version`),
your Python version, your OS, and what `ansible --version` prints. If a command
pb built was wrong, paste the command line from the right-hand pane — that is
usually the whole bug.

Security issues go through
[private reporting](https://github.com/thei1575/ansible-pb/security/advisories/new)
instead, not a public issue. See [Security](security.md).
