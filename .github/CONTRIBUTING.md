# Contributing to pb

Contributions should make repository inspection or Ansible operations clearer,
safer, or more reliable while preserving the project rules below.

## Ground rules

* **Ansible owns execution semantics.** Infrastructure actions invoke
  `ansible-playbook`, `ansible-inventory`, or `ansible-vault`. The interface
  presents the exact command before it runs. Patches must preserve that
  boundary.
* **Shell commands run in workers.** Anything that shells out is slow enough to
  freeze Textual. Use a `@work(thread=True)` worker, as the existing code does.
* **Secrets stay hidden by default.** `ansible-inventory` decrypts vaults, so
  anything credential-shaped is masked until the user asks. If you add a new
  view over inventory data, run it through `meta.redact()`.
* **Read views do not mutate state.** Inventory, Status, Roles, and Doctor are
  read operations. Playbooks and Vault contain the write operations, which run
  through Ansible.
* **A plugin must not be able to take pb down.** Everything in
  `src/pb/plugins/` that calls into plugin code catches whatever comes out,
  reports it, and switches that plugin off for the session. A new hook goes
  through `PluginHost`, never straight from a widget.
* **The plugin API is versioned.** `pb.plugins.api` is what third-party code
  imports. Adding an optional hook is fine; changing or removing one means
  bumping `API_VERSION`, which makes pb refuse every plugin written for the old
  number. See [Writing a plugin](https://thei1575.github.io/ansible-pb/reference/writing-plugins/).

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
in CI and the tests do not need it - anything that shells out is tested against
a fixture repo on disk, or not at all.

### Tests

`tests/conftest.py` builds a throwaway Ansible repo in `tmp_path` (an
`ansible.cfg`, a couple of playbooks, a role, an inventory and a vault). Use
the `repo` fixture rather than mocking `Path`. Tests must not need a network,
an SSH key, or an `ansible` binary.

`Repo.discover` reads `$ANSIBLE_INVENTORY`, so an autouse fixture clears it -
a developer who has it exported must not get different results from CI. If you
add anything else that reads the environment, clear it the same way.

Everything pb writes outside the repo - what the update check remembers and
which plugins are installed - sits in one `config_dir()`, and an autouse
fixture points `$PB_HOME` at `tmp_path` so a test never reads, installs into,
or overwrites the config of whoever is running it. The `make_plugin`,
`linked_plugin` and `plugin_git_repo` fixtures build plugins on disk, the last
one in a local git repository - installing "from GitHub" is cloning a git URL,
and a directory is such a URL, so the install path is tested end to end
without a network. `tests/test_plugin_app.py` drives a real headless Textual
app, because a tab that is not mounted and a key that is not bound are
failures no unit test sees.

## The documentation site

The site under [thei1575.github.io/ansible-pb](https://thei1575.github.io/ansible-pb/)
is [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) over the
Markdown in `docs/`. Serve it with live reload:

```bash
uv run --group docs mkdocs serve
```

Build it the way CI does, which fails on a broken internal link or a missing
snippet:

```bash
uv run --group docs mkdocs build --strict
```

The changelog, this file and `SECURITY.md` have one home each - the repo root
and `.github/`. The site includes them with `pymdownx.snippets` rather than
keeping a second copy, so **links inside them must be absolute**: a
repo-relative link renders correctly on GitHub and 404s on the site.

A change to how pb behaves belongs in `docs/` in the same pull request. The
pages that go stale fastest are `docs/reference/keys.md` and
`docs/reference/files.md` - both enumerate things the code owns.

## Commit messages

Write the subject line as what the change does for the user, in the
imperative - `Mask cert private keys in the inventory tab`, not
`fix(meta): redaction`. The existing history is the guide.

## Reporting a bug

Open an issue with the template. Include the pb version (`pb --version`), your
Python version, your OS, and what `ansible --version` prints. If a command
pb built was wrong, paste the command line from the right-hand pane - that is
usually the whole bug.

Please do **not** file security issues in public. See
[SECURITY.md](https://github.com/thei1575/ansible-pb/blob/main/.github/SECURITY.md).
