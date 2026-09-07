# Plugins

<kbd>8</kbd>

Plugins adapt pb to operations specific to your infrastructure. Each plugin is
a Git repository containing a manifest and Python module. Plugins can add tabs,
key actions, [Doctor](doctor.md) checks, command-palette entries, run hooks,
detail-pane sections, and status-bar data. They can also replace a built-in key
action.

<div class="pb-keys" markdown>

| Key | Does |
|---|---|
| <kbd>i</kbd> | Install one from GitHub |
| <kbd>u</kbd> | Update the selected plugin |
| <kbd>e</kbd> | Enable or disable it |
| <kbd>r</kbd> | Remove it |
| <kbd>o</kbd> | Everything pb knows about it, including a load failure |

</div>

## Developer documentation

| Page | Use it for |
|---|---|
| [First plugin](../plugins/quickstart.md) | Scaffold, link, run, and inspect a working plugin |
| [Architecture and lifecycle](../plugins/architecture.md) | Loader stages, hook order, threads, state, and failure handling |
| [Hook cookbook](../plugins/hooks.md) | Tabs, actions, commands, run policy, Doctor checks, and status output |
| [Testing and debugging](../plugins/testing.md) | Unit tests, headless Textual tests, isolated config, and load failures |
| [Packaging and distribution](../plugins/distribution.md) | Repository layout, releases, refs, updates, and private Git hosts |
| [API reference](../reference/writing-plugins.md) | Manifest fields, classes, dataclasses, hooks, and built-in action names |

## Columns

| Column | Comes from |
|---|---|
| Plugin | the `name` in its `pb-plugin.toml` |
| Version | the `version` in the same file |
| State | `✔ loaded`, `• pending restart`, `disabled`, or `✘` and the stage it failed at |
| Where from | what you typed when you installed it, or the directory it is linked to |
| What it adds | its one-line `summary` |

The detail pane shows the checked-out ref and commit, installation directory,
and implemented hooks.

## Installing

<kbd>i</kbd> asks for a source, then shows what it is about to clone and what
installing means before anything is fetched. The same thing from a shell:

```bash
pb plugin install owner/pb-terraform         # GitHub
pb plugin install owner/pb-terraform@v1.2.0  # pinned to a tag
pb plugin install owner/pb-terraform --ref abc123
pb plugin install git@github.internal:ops/pb-mine.git
pb plugin install https://gitlab.example/ops/pb-mine.git#v2
```

`owner/repo` means GitHub, because that is where pb plugins are published.
Anything with a scheme, an `scp`-style `git@host:path`, or a path to a local
repository is handed to `git` untouched, so a private mirror needs nothing
from pb.

A pinned install stays pinned: `pb plugin update` re-resolves the same ref
rather than drifting onto a branch. An unpinned one fast-forwards to the
remote's default branch.

## Restart requirement

Installing, updating, enabling, and removing take effect the next time pb
starts. Plugin code is imported once during startup. A restart keeps tabs,
actions, and loaded Python modules on the same plugin version.

The messages say so, and the state on the tab distinguishes `✔ loaded` from
`• pending restart` precisely so you can tell which version you are looking
at.

## When a plugin breaks

pb catches everything a plugin's hooks raise. The plugin is switched off for
the rest of the session, its tabs are removed, its replaced actions are handed
back to the built-ins, a notification names the hook that failed, and it
becomes a failed check on the [Doctor](doctor.md) tab. pb keeps running.

<kbd>o</kbd> shows the traceback for the disabled plugin.

If pb misbehaves and you are not sure a plugin is to blame, start it without
any:

```bash
pb --no-plugins        # PB_NO_PLUGINS=1 does the same
```

A plugin that will not even import is faster to diagnose from a shell, which
prints the traceback without starting the TUI:

```bash
pb plugin doctor
```

## Trust boundary

A plugin is Python running inside pb with your permissions. It can read the
repository and `.vault_pass`, change the `ansible` commands pb builds, and
replace key actions. Plugins have no sandbox. Installation requires an explicit
decision:

- Installing asks first, and prints the URL it is about to clone. `--yes`
  skips the prompt; with no terminal to ask in, `pb plugin install` refuses
  rather than installing silently.
- **Plugin code first runs at application startup.** Installation only clones
  the repository and records its metadata.
- Every install records the exact commit. `pb plugin info <name>` shows it,
  and the checkout is an ordinary Git repository that can be inspected with
  `git log`.
- `pb plugin disable <name>` keeps a plugin installed but stops loading it.

Read a plugin before you install it, the way you would read a shell script
someone sent you. See also
[Security](https://github.com/thei1575/ansible-pb/blob/main/.github/SECURITY.md).

## Installation path

Under [pb's config directory](../reference/files.md#writes-in-your-home-directory),
not in your Ansible repo: which plugins you have installed is about your
machine, not about the repo you are pointing pb at.
