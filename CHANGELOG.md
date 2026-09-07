# Changelog

All notable changes to pb are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and pb aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) from 1.0 onward.
Before then, minor versions may break things.

## [Unreleased]

### Added

* **pb tells you when there is a newer pb.** Once a day at startup it asks
  GitHub for the latest release, and if there is one it shows the changelog
  entries between the version you are running and that one, along with the
  exact command that would install it. Accept and pb runs that command and
  tells you to restart; skip and that version is never offered again; escape
  and it asks again tomorrow. `ctrl+u` checks on demand, ignoring both the
  interval and anything you skipped. Doctor names the version you are running
  and how it was installed.
* The install command is built for however pb was installed — `uv tool
  install --force`, `pipx install --force` or `pip install --upgrade` — and
  pins the tag, because `uv tool upgrade` on a git URL keeps the ref it was
  installed with and would report success without changing anything. A clone
  installed with `-e` is not touched: pb says to `git pull` instead.
* This is the only network connection pb makes on its own: one unauthenticated
  GET to `api.github.com` sending nothing but a `pb/<version>` User-Agent, and
  the repository's `CHANGELOG.md` when there is something to show. `pb
  --no-update-check` or `PB_NO_UPDATE_CHECK=1` turns it off. Which version you
  skipped and when pb last looked live in `~/.config/pb/update.json`.
  [SECURITY.md](https://github.com/thei1575/ansible-pb/blob/main/.github/SECURITY.md)
  says so in full — it previously promised
  pb made no network connections at all, and no longer can.
* **The inventory path is no longer fixed at `inventories/production`.** pb
  follows Ansible's own precedence — `-i/--inventory`, then
  `$ANSIBLE_INVENTORY`, then `[defaults] inventory` in `ansible.cfg` — so a
  repo where Ansible already works needs no configuring. Failing all three it
  looks around: `inventories/<env>/` under any name, `inventory/`, or a
  `hosts.yml`, `hosts.ini` or `inventory.yml` at the root. `group_vars` and the
  vaults are then read from beside whichever inventory won, as Ansible resolves
  them.
* pb passes `-i` to `ansible-playbook` and `ansible-inventory` whenever the
  path came from somewhere Ansible would not look itself, so the host list pb
  shows before an apply is the one Ansible will use. When the path came from
  `ansible.cfg` or the environment, pb passes nothing and leaves a multi-source
  setting intact.
* Doctor names the inventory pb settled on, where that came from, and whether
  it exists.
* A test suite (`tests/`, COUNT tests) covering inventory resolution, repo
  discovery, playbook, role and vault parsing, recap parsing, the pty streamer,
  secret redaction, the SSH probe's accessors, the CLI and the run history —
  the update check and the prompt it puts on screen — all against a fixture
  Ansible repo built in `tmp_path`. No `ansible` binary, no network.
* GitHub Actions CI: `ruff check` plus the tests on Python 3.11, 3.12 and 3.13,
  once more on macOS for the pty handling, and a job that builds the sdist and
  wheel, installs the wheel clean and checks `pb --version` and that `pb.tcss`
  shipped.
* Contributor documentation under `.github/`: `CONTRIBUTING.md` (the invariants
  a patch has to hold), `SECURITY.md` (what pb touches on your machine and your
  hosts, and how to report privately), `CODE_OF_CONDUCT.md`, issue forms and a
  pull-request template.
* A documentation site at
  [thei1575.github.io/ansible-pb](https://thei1575.github.io/ansible-pb/) —
  [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) over
  `docs/`, with a page per tab, the inventory resolution rules worked through,
  a full key map, troubleshooting, and an inventory of every file and process
  pb touches. CI builds it with `--strict` on every pull request, so a broken
  link fails the build; pushes to `main` publish it to GitHub Pages. The
  changelog, `CONTRIBUTING.md` and `SECURITY.md` are included into the site
  rather than copied.
* `.editorconfig`, a Dependabot schedule, and `dev` and `docs` dependency
  groups so `uv sync` gets ruff and pytest and
  `uv run --group docs mkdocs serve` gets the site.

### Fixed

* **A row-highlight event dispatched after its pane had gone took the app
  down.** Filling a table queues one per row, and they are handled afterwards
  — including while pb is shutting down, when the detail pane they would draw
  into no longer exists. Quitting while the initial load was still running
  could end in a traceback. There is nothing to redraw at that point, so
  nothing is.
* **A run could lose its output on macOS, PLAY RECAP included.** The parent
  closed the pty slave as soon as the child was spawned, so the master reported
  EOF the moment the child exited — and on BSD that EOF discards whatever is
  still in the pty buffer. A short command could lose everything it printed.
  The parent now keeps the slave open for the length of the read loop, which
  ends on the child exiting with a drained buffer rather than on EOF. Found by
  the macOS CI run, which is why it is there.
* An inventory that made Ansible print a warning was reported as
  "could not parse ansible-inventory output". `capture()` merges stderr into
  stdout and `ansible-inventory` warns on stderr, so the JSON was never the
  whole output. pb now finds the JSON, keeps the warning, and shows it — so
  "no hosts" says why instead of looking like a pb bug.
* `git_diff` built its separator with an f-string that had nothing to
  interpolate.
* Dropped two unused imports (`textual.widgets.Label` in `app.py`,
  `pathlib.Path` in `run.py`).
* Lines over the project's own 100-column limit in `app.py` and the SSH probe
  script; `ruff check` now passes on the whole tree.

## [0.1.0] — 2026-09-07

First release, extracted from the Ansible repo it grew up in.

### Added

* **Playbooks** — run, dry-run or syntax-check any playbook, with `--tags` and
  `--limit` pickers, and a pane showing the exact `ansible-playbook` command
  the current options produce.
* **Blast radius on apply** — the real host list is resolved through
  `--list-hosts` and the hosts and addresses are named before you confirm.
* **Inventory** — hosts, groups and resolved variables from
  `ansible-inventory`, with credential-shaped values masked until revealed;
  ping, gather facts, or open an ssh session.
* **Status** — a read-only SSH health probe per host: uptime, load, disk,
  memory, pending updates, failed units, running containers and certificate
  expiry.
* **Roles** — task files, defaults, and which playbooks use each role.
* **Vault** — view, edit, create and rekey the per-group vaults through
  `ansible-vault`.
* **History** — every run pb has made, recorded under `.pb/runs/` with the
  command, tags, exit code, recap, the commit it ran against and the full
  captured output.
* **Doctor** — a preflight over the whole repo.
* Uncommitted playbooks and roles are marked with a yellow `●`; `ctrl+g` shows
  the working-tree diff.

[Unreleased]: https://github.com/thei1575/ansible-pb/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/thei1575/ansible-pb/releases/tag/v0.1.0
