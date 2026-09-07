# Architecture

pb separates repository inspection, command execution, run presentation,
history, host probes, plugins, updates, and interface components into focused
modules. Five project rules govern changes across those modules.

## The invariants

### Ansible owns execution semantics { #ansible-owns-execution-semantics }

Infrastructure actions invoke `ansible-playbook`, `ansible-inventory`, or
`ansible-vault`, with the exact command visible before execution.

The tag picker uses `--list-tags`, the host list uses `--list-hosts`, and the
inventory comes from `ansible-inventory --list`. Vault writes use
`ansible-vault`. This boundary keeps execution behaviour aligned with the
repository's Ansible installation, configuration, and plugins.

The Roles view indexes direct `roles:` declarations. Following `include_role`
would require task-semantic parsing, so dynamic role use remains outside that
index.

### Shell commands run outside the UI thread

Anything that shells out is slow enough to freeze Textual. Every such call goes
through a `@work(thread=True)` worker and comes back with `call_from_thread`.

The Status probe fans out across a `ThreadPoolExecutor` capped at eight, so one
slow host does not hold up the fleet. Doctor is `exclusive=True`, so pressing
<kbd>r</kbd> twice does not run it twice.

### Secrets stay hidden by default

`ansible-inventory --list` decrypts the vaults to resolve variables, so
plaintext credentials arrive in pb's memory whether it wants them or not.
Anything credential-shaped is masked until the user asks. Any new view over
inventory data has to run through `meta.redact()`.

### Read views preserve state

Inventory, Status, Roles and Doctor must not mutate a host or the repo. Only
Playbooks and Vault write, and only through Ansible.

### Plugin failures are contained { #a-plugin-cannot-take-pb-down }

pb imports third-party code into its own process, which means the console's
reliability would otherwise be the reliability of the least careful plugin
installed.

Every call into plugin code goes through `PluginHost`. It catches exceptions,
switches the plugin off for the rest of the session, removes its tabs, restores
replaced built-in actions, and adds the failure to
[Doctor](../guide/doctor.md). Other application features remain available.

The other half of it is that the plugin surface is *versioned*.
`pb.plugins.api` is what third-party code imports; adding an optional hook is
free, and changing or removing one means bumping `API_VERSION`, which makes pb
refuse every plugin written against the old number rather than importing it
and failing somewhere in the middle. The manifest carries that number and is
read before a single line of plugin code is imported.

## The modules

```
src/pb/
  app.py          the App, the tabs, and every key binding      (1836)
  meta.py         read-only introspection of the Ansible repo    (579)
  update.py       checking GitHub for a newer pb                 (342)
  widgets.py      the modal pickers, prompts and viewers         (254)
  run.py          the full-screen run view                       (208)
  runner.py       running ansible on a pty and streaming it back (195)
  pb.tcss         the stylesheet                                 (183)
  hoststatus.py   the read-only SSH health probe                 (130)
  history.py      the durable record under .pb/runs/             (129)
  config.py       where pb keeps what is not about the repo       (27)
  plugins/        the plugin system                              (1691)
    cli.py          `pb plugin …`                                (322)
    host.py         binding plugins into the running app         (287)
    api.py          what a plugin imports - the versioned surface (283)
    scaffold.py     `pb plugin new`                              (256)
    source.py       resolving owner/repo, and cloning it          (239)
    loader.py       importing plugin code, failures contained     (216)
    manage.py       install, update, link, remove                 (215)
    store.py        what is installed, and where                  (153)
    manifest.py     pb-plugin.toml, read before any plugin code   (139)
```

### `meta.py` - what pb knows

Everything the UI knows about playbooks, inventory, roles and vaults is derived
here, and nothing here knows about Textual.

The centre of it is `Repo`, a frozen dataclass of `(root, inventory,
inventory_origin)`. `Repo.discover` implements
[inventory resolution](../reference/inventory-resolution.md); the origin it
records is what `inventory_args` uses to decide whether pb should pass `-i` at
all, and what Doctor prints. Keeping the origin rather than just the path is
what makes that decision possible later.

`redact()` and `SECRET_KEY_RE` live here too, next to the code that loads the
plaintext - deliberately, so the masking is impossible to miss when you touch
the loader.

### `runner.py` - the pty

The child gets a pty rather than a pipe, because Ansible only emits colour when
it believes it is talking to a terminal, and looking at that output is the point
of the tool. It also gets `start_new_session=True`, so cancelling can kill the
whole process group - the forks Ansible spawned, not just Ansible.

The parent keeps the pty slave open for the length of the read loop. Closing it
after the spawn makes the master report EOF the moment the child exits, and on
BSD that EOF discards whatever is still sitting in the pty buffer - which is
where the last lines of a run live, `PLAY RECAP` included. A short command can
lose its output entirely that way.

With a writer still open, no EOF ever arrives, so the loop ends the way it was
written to: the child is gone *and* a zero-timeout `select` says the buffer has
drained. That `_drain_ready` check is also what gives a dying child the chance
to flush, which is why cancelling still shows you what it managed to print.

This is exactly the class of bug that only appears on one platform, which is why
CI runs the suite once on macOS.

### `run.py` - the run view

Owns one command from spawn to record. The worker appends lines to a `deque`; a
timer drains it into a `RichLog` every 80 ms and re-renders the status line,
which is how a run that prints thousands of lines stays responsive. The recap is
re-parsed on each tick so the counters update live.

When the run ends it writes the [history](../guide/history.md) record - from the
run view, not the app, so nothing has to remember to do it.

### `history.py` - the record

A JSON sidecar plus the captured output, per run, under `.pb/runs/`. `record()`
is written to never raise: losing history must not kill a run.

### `hoststatus.py` - the probe

One compound shell script, fed to `ssh … bash -s` on **stdin** so nothing has to
survive shell quoting. It emits `key=value` lines and omits anything
unavailable, which is what keeps it portable across whatever a host runs. It
only ever reads. See [Status](../guide/status.md).

### `app.py` - the tabs

The `App`, the eight tabs, and every binding.

Two structural things:

**Bindings live on the table that owns the verb**, not on the app, so the footer
only ever offers what the focused tab can actually do - which is why <kbd>r</kbd>
is "run" in Playbooks and "refresh" in Status. The *actions* live on the app,
hence the explicit `app.` namespace in each `Binding`: a widget binding does not
bubble on its own.

**A `TabPane` only stays active while focus is inside it.** A focused widget in
another pane posts `TabPane.Focused` and yanks the tab back, so switching tabs
has to move focus into the new pane, which is what `_focus_pane` is for.

### `plugins/` - the extension points

`api.py` is the whole third-party surface: the `Plugin` base class whose every
method is optional, and the dataclasses for what a plugin contributes. Nothing
else in the package is something a plugin imports.

`host.py` is the only module that knows both sides. It takes what a plugin
contributes and puts it into the widget tree - panes through
`TabbedContent.add_pane`, keys through the target widget's own `BindingsMap`,
and actions by setting `action_<name>` on the app instance, which is exactly
how Textual dispatches them. That last one is why replacing a built-in needed
no per-action plumbing, and why `base_action()` can hand back what was there
before.

Installing and importing are kept apart on purpose. `manage.py` and
`source.py` clone and record; `loader.py` imports. Nothing a plugin ships runs
at install time, and the manifest - including its API version - is read before
any of its code is.

One ordering detail worth knowing: `before_run` hooks fire in
`_authorize`, *before* the apply confirmation is built, so a plugin that
rewrites `argv` cannot leave the user approving a different command. The rule
that pb only runs what it has shown you survives plugins.

## The test suite

`tests/` builds a throwaway Ansible repository in `tmp_path` - an
`ansible.cfg`, a couple of playbooks, a role, an inventory and a vault - and
runs against that. It needs **no `ansible` binary and no network**, which is why
CI can run it on four interpreters in under a minute.

| File | Covers |
|---|---|
| `test_inventory.py` | inventory resolution and `ansible-inventory` parsing |
| `test_repo.py` | repo discovery and the `Repo` accessors |
| `test_meta.py` | playbook, role and vault parsing, redaction |
| `test_runner.py` | the pty streamer and recap parsing |
| `test_hoststatus.py` | the probe's accessors |
| `test_history.py` | the run record |
| `test_cli.py` | argument handling and the exit codes |
| `test_update.py` | version comparison, the GitHub calls, the upgrade command |
| `test_app_update.py` | the update prompt, and skipping a version |
| `test_plugin_manifest.py` | `pb-plugin.toml`, and everything it refuses |
| `test_plugin_store.py` | the state file, including it being corrupt |
| `test_plugin_install.py` | source resolution, install, update, pin, link, remove |
| `test_plugin_loader.py` | importing plugin code, and every way it can fail |
| `test_plugin_app.py` | plugins in a real headless app |
| `test_plugin_cli.py` | `pb plugin …` and its refusals |

Use the `repo` fixture rather than mocking `Path`. `Repo.discover` reads
`$ANSIBLE_INVENTORY`, so an autouse fixture clears it. A developer who has it
exported must not get different results from CI. Another points `$PB_HOME` at
`tmp_path`, keeping update state and installed plugins out of the developer's
configuration.

Plugin installation tests clone from local git repositories. The
`plugin_git_repo` builds one and the install, update and pin paths run end to
end without network access. `test_plugin_app.py` drives a real Textual app in
headless mode to verify tab mounting and key bindings.

## Wanting to change something

[Contributing](contributing.md) has the setup, the checks to run, and what a
commit message should look like.
