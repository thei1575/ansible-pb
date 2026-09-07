# Packaging and distribution

A distributable plugin is a Git repository with `pb-plugin.toml` at its root.
pb installs the repository itself, records the resolved commit, and imports the
module on the next application start.

## Repository contract

```text
pb-policy/
├── pb-plugin.toml
├── pb_policy/
│   ├── __init__.py
│   ├── policy.py
│   └── style.tcss
├── tests/
├── README.md
└── LICENSE
```

Python packaging metadata is optional because pb adds manifest `python_path`
entries directly to `sys.path`. Include `pyproject.toml` when the plugin also
ships as a Python package or needs its own dependency and test configuration.

## Manifest for a release

```toml
[plugin]
name = "pb-policy"
version = "1.4.0"
summary = "Change policy and maintenance-window checks"
api = 1
module = "pb_policy"
homepage = "https://github.com/acme/pb-policy"
python_path = ["."]
css = ["pb_policy/style.tcss"]
```

Names contain lowercase letters, digits, `.`, `_`, and `-`, start with a
letter or digit, and are limited to 64 characters. Module names must be valid
Python identifiers and cannot use `pb` or its submodules.

All paths are relative to the repository root. Absolute paths and paths that
escape through `..` are rejected.

## Version policy

The manifest `version` is display metadata. Git refs and recorded commits
control installation. A practical release sequence is:

1. Update `version` and the changelog.
2. Run the plugin test suite and `pb plugin doctor` against a linked checkout.
3. Commit the release state.
4. Tag the commit, for example `v1.4.0`.
5. Test a clean install pinned to that tag.

Declare the current plugin API number in every release. pb refuses a different
number before importing the module.

## Install forms

```bash
pb plugin install acme/pb-policy
pb plugin install acme/pb-policy@v1.4.0
pb plugin install acme/pb-policy --ref release/1.x
pb plugin install https://gitlab.example/ops/pb-policy.git#v1.4.0
pb plugin install git@github.internal:ops/pb-policy.git
pb plugin install /srv/git/pb-policy
```

`owner/repo` resolves through GitHub. URLs, SSH Git syntax, and local Git
repositories are passed to Git. Private repositories use the operator's
existing Git credentials and SSH configuration.

## Updates and refs

An install without a ref follows the remote default branch when
`pb plugin update` runs. An install with a tag, branch, or commit re-resolves
that same ref. Every installed record stores the source, ref, resolved commit,
manifest version, and enabled state.

`pb plugin update` does not modify linked working copies. Developers control
those directories directly.

## Dependencies

Plugin imports run in pb's Python environment. Prefer the standard library and
packages pb already depends on. Document any extra dependencies and install
them into the same environment as pb. A missing dependency appears as an
`import` stage failure in `pb plugin doctor`.

Avoid writing dependency files into the managed plugin checkout at runtime.
Updates may replace that checkout. Runtime state and caches belong under
`self.data_dir`.

## Release compatibility

Record these fields in the README:

| Field | Example |
|---|---|
| pb plugin API | `1` |
| tested pb releases | `0.8.x` |
| Python requirement | `3.12+` |
| external programs | `terraform >= 1.8` |
| supported platforms | Linux, macOS |

Use Doctor checks for dependencies whose presence can vary per machine. Import
failures should be reserved for dependencies required to load any part of the
plugin.

## Release checklist

- The manifest loads and its paths stay inside the repository.
- The module name is unique and importable.
- A clean environment can install the plugin from its public or private URL.
- The tag points to the commit containing the matching manifest version.
- The README documents permissions, subprocesses, network calls, and files
  written by the plugin.
- Secrets stay out of logs, notifications, run labels, and plugin data files.
- A pinned install survives `pb plugin update` without switching refs.
- The plugin handles an empty inventory and repositories with no prior runs.

Operators can verify a release with:

```bash
pb plugin install acme/pb-policy@v1.4.0
pb plugin info pb-policy
pb plugin doctor
```
