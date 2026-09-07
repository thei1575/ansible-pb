# Changelog

All notable changes to pb are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and pb aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) from 1.0 onward.
Before then, minor versions may break things.

## [Unreleased]

### Added

* A test suite (`tests/`, 93 tests) covering repo discovery, playbook, role and
  vault parsing, the resolved inventory, recap parsing, the pty streamer,
  secret redaction, the SSH probe's accessors and the run history — all against
  a fixture Ansible repo built in `tmp_path`. No `ansible` binary, no network.
* GitHub Actions CI: `ruff check` plus the tests on Python 3.11, 3.12 and 3.13,
  once more on macOS for the pty handling, and a job that builds the sdist and
  wheel, installs the wheel clean and checks `pb --version` and that `pb.tcss`
  shipped.
* Contributor documentation under `.github/`: `CONTRIBUTING.md` (the invariants
  a patch has to hold), `SECURITY.md` (what pb touches on your machine and your
  hosts, and how to report privately), `CODE_OF_CONDUCT.md`, issue forms and a
  pull-request template.
* `.editorconfig`, a Dependabot schedule, and a `dev` dependency group so
  `uv sync` gets ruff and pytest.

### Fixed

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
