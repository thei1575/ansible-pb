# Writing a plugin

A pb plugin is a git repository with a manifest and an importable Python
module. pb clones it, imports it at start-up, and lets it add tabs, keys and
[Doctor](../guide/doctor.md) checks, react to every run, or replace something
the base app already does.

This page is the API reference. Start with [Build your first plugin](../plugins/quickstart.md).
The [hook cookbook](../plugins/hooks.md) provides complete patterns, and
[Architecture and lifecycle](../plugins/architecture.md) covers ordering,
threads, state, and failure handling. For installation and trust, see
[Plugins](../guide/plugins.md).

## Create a plugin

```bash
pb plugin new pb-mine        # writes a working plugin and inits a git repo
cd pb-mine
pb plugin link .             # pb reads this directory in place
pb plugin doctor             # does the manifest parse? does it import?
pb ~/my-ansible-repo         # there is your tab
```

`pb plugin new` scaffolds a working plugin that demonstrates most hooks. Remove
the hooks your plugin does not need, edit the remaining implementation, and
restart pb to load the change. Plugin code is imported once during startup.

When it works, push it to GitHub and anyone can install it:

```bash
pb plugin install your-name/pb-mine
```

## Layout

```
pb-mine/
  pb-plugin.toml      the manifest - pb reads this before importing anything
  pb_mine/
    __init__.py       the module, defining a Plugin subclass
    style.tcss        optional stylesheet, loaded with pb's own
  README.md
```

A single `pb_mine.py` beside the manifest works just as well as a package.

### The manifest

```toml
[plugin]
name = "pb-mine"                  # required: lowercase, digits, - _ .
version = "0.1.0"
summary = "One line, shown on the Plugins tab"
api = 1                           # the plugin API this was written for
module = "pb_mine"                # default: the name with - and . flattened
homepage = "https://github.com/your-name/pb-mine"
python_path = ["."]               # added to sys.path, relative to the plugin
css = ["pb_mine/style.tcss"]      # loaded alongside pb.tcss
```

`api` is the contract. pb refuses a plugin declaring a different number rather
than importing it and failing halfway; `pb plugin doctor` prints the version
this pb speaks. Nothing in the manifest may point outside the plugin
directory, and `module` may not be `pb`.

Two installed plugins cannot declare the same `module` - they share
`sys.path`, so one would shadow the other. pb reports that instead of picking.

## The Plugin class

```python
from pb.plugins import Plugin


class Mine(Plugin):
    def activate(self) -> None:
        self.notify(f"reading {self.repo.root}")
```

pb instantiates every `Plugin` subclass your module defines. To be explicit -
or to keep a base class out of it - set `PB_PLUGIN` to the class, an instance,
or a list:

```python
PB_PLUGIN = Mine
```

Before `activate()` runs, pb fills in `name`, `version`, `summary`, `root`
(your directory), `data_dir` (a private directory for your own state) and
`app`. Every hook is optional.

### Available state

| | |
|---|---|
| `self.repo` | the `meta.Repo`: root, inventory, `inventory_args` |
| `self.playbooks` `self.roles` `self.vaults` | what pb discovered |
| `self.inventory` | hosts, groups and resolved vars |
| `self.host_status` | the Status tab's last SSH probe, by host |
| `self.runs` | the history under `.pb/runs` |
| `self.app` | the whole `PbApp`, for anything the list above does not cover |

`meta` is read-only introspection you can call yourself:
`meta.capture(argv, cwd)` shells out and returns `(code, output)`,
`meta.redact(vars)` masks anything credential-shaped.

### Available operations

| | |
|---|---|
| `self.launch(argv, label, mode="ad-hoc")` | run a command the way pb runs its own - full screen, streamed, recorded in history. `mode` is what the hooks see |
| `self.notify(message, severity=…, timeout=5)` | a toast |
| `self.view(title, body, lexer=None)` | pb's scrollable viewer |
| `self.reload()` | re-read the repo and repaint every tab |
| `self.base_action(name)` | the action you replaced, so you can wrap it |
| `self.data_dir` | somewhere to keep your own state |

## The hooks

### `activate()` and `reloaded()`

`activate()` runs once, after your tabs are mounted and before the repo has
been read. Add columns here. `reloaded()` runs every time pb has re-read the
repo - on start-up, on `ctrl+r`, and after every run - which is where a tab of
your own fills itself in.

```python
def activate(self) -> None:
    self.app.query_one("#mine-table", DataTable).add_columns("Host", "Drift")

def reloaded(self) -> None:
    table = self.app.query_one("#mine-table", DataTable)
    table.clear()
    for host in self.inventory.hosts:
        table.add_row(host.name, "-")
```

`deactivate()` runs when pb exits cleanly.

### `tabs()` - a tab of your own

```python
def tabs(self):
    yield TabSpec(
        id="tab-mine",
        title="Drift",
        factory=self._pane,          # called once; returns the widget
        focus="#mine-table",         # must name something focusable
        after="tab-status",          # default: last
    )

def _pane(self):
    return Horizontal(
        MyTable(cursor_type="row", zebra_stripes=True, id="mine-table"),
        VerticalScroll(Static("", id="mine-detail", classes="detail-body"),
                       classes="detail"),
        classes="split",
    )
```

`classes="split"` and `classes="detail"` are pb's own, so a plugin tab looks
like a built-in one. `focus` has to name a focusable widget - a `DataTable`,
an `Input`, a container with `can_focus` - because key bindings on your
widgets do not fire until something inside the pane has focus.

### `keys()` and `actions()` - including replacing pb's own

Bindings live on the widget that owns the verb, as they do in pb, so the
footer offers them only while that tab has focus. `target` is a widget id -
`playbooks`, `hosts`, `roles`, `vaults`, `status`, `history`, `doctor`,
`plugins`, one of yours - or the literal `app` for a binding that works
everywhere.

```python
def keys(self):
    yield KeySpec(target="hosts", key="D", action="app.show_drift", description="Drift")

def actions(self):
    return {"show_drift": self.show_drift}
```

An action name pb already uses **replaces** the built-in. This is how a plugin
changes what the base app does rather than only adding to it:

```python
def actions(self):
    return {"run": self.run_with_a_ticket}

def run_with_a_ticket(self):
    if not self.change_ticket_open():
        self.notify("no open change ticket", severity="error")
        return
    self.base_action("run")()          # then do what pb would have done
```

`base_action(name)` returns whatever was there before *your* plugin took over
- the built-in, or an earlier plugin's replacement. Plugins are loaded in
install order, so the last one to claim a name wins; `pb plugin list` shows
that order.

pb's own actions, all replaceable this way:

| Tab | Actions |
|---|---|
| Playbooks | `run` `check` `syntax` `tags` `limit` `diff` `verbosity` `extra` `clear` `open` |
| Inventory | `ping` `facts` `inspect` `reveal` `ssh` |
| Status | `refresh_status` |
| Roles | `defaults` `tasks` |
| Vault | `view` `edit` `new` `rekey` |
| History | `show_log` `rerun` |
| Doctor | `recheck` |
| Plugins | `plugin_install` `plugin_update` `plugin_toggle` `plugin_remove` `plugin_info` |
| Global | `help` `reload` `changes` `quit` `tab` |

### `commands()` - the command palette

```python
def commands(self):
    yield Command(title="Re-probe drift", callback=self.show_drift, help="ctrl+p")
```

### `doctor()` - extra preflight checks

Runs in a worker thread, so it may shell out.

```python
def doctor(self):
    code, out = meta.capture(["terraform", "version"], self.repo.root)
    yield CheckResult("terraform", code == 0, out.splitlines()[0] if out else "not found")
```

`ok` is `True` for a pass, `False` for a failure, `None` for a warning - the
same three states the built-in checks use.

### `before_run()` - inspect, edit or stop a command

```python
def before_run(self, request: RunRequest) -> None:
    if request.mode == "run" and self.is_frozen():
        request.veto("change freeze until Monday")
        return
    request.env["ANSIBLE_CALLBACKS_ENABLED"] = "profile_tasks"
    request.argv = [*request.argv, "--diff"]
```

`request.mode` is `run`, `check` or `syntax` for a playbook, `repeat` for a
re-run from History, `ssh` or `vault` for the things that leave the TUI, and
`ad-hoc` for ping, facts and anything a plugin launched itself.

Whatever `argv` ends up as is both what executes **and** what the user is
shown: the hooks run before the confirmation dialog, so pb never runs a
command it has not displayed. `request.env` is merged into the child's
environment. `veto()` stops the run and names your plugin in the message.

### `after_run()` - once it has finished and been recorded

```python
def after_run(self, result: RunResult) -> None:
    if result.ok and result.run:
        self.post_to_slack(result.label, result.recap, result.run.git_sha)
```

`result` carries `argv`, `label`, `exit_code`, `duration`, the parsed
`recap`, every output `line`, and `run` - the `history.Run` just written to
`.pb/runs`.

This fires for the runs pb streams on the run screen, which are the ones it
records. Anything that leaves the TUI for a real terminal - an ssh session,
`ansible-vault edit`, a playbook with `vars_prompt` - is not recorded and does
not arrive here. `before_run` still sees all of them.

### `detail()` - add to a core detail pane

```python
def detail(self, pane: str, subject) -> Text | None:
    if pane == "host":
        return Text(f"\ndrift: {self.drift_for(subject.name)}\n", style="yellow")
    return None
```

`pane` is one of `playbook`, `host`, `role`, `vault`, `status`, `history`, and
`subject` is the object that pane is showing. A plain `str` is accepted too,
here and in `status_bar()`.

### `status_bar()` - a segment on the top strip

```python
def status_bar(self) -> Text | None:
    return Text(f"  drift {len(self.drifted)}", style="yellow" if self.drifted else "dim")
```

## When a plugin breaks

pb catches exceptions raised by hooks. The plugin is switched off for the rest
of the session, its tabs are removed, a notification identifies the failed
hook, and Doctor records the failure. Other application features remain
available.

While developing, `pb plugin doctor` is faster than starting the TUI: it loads
every plugin, prints the hooks each one overrides, and prints the traceback
for any that will not import.

Threads: `doctor()` runs in a worker thread. Every other hook runs on the UI
thread and must not block - use `self.app.run_worker(…, thread=True)` or
`self.launch()` for anything that shells out. This is pb's own rule, for the
same reason: Textual freezes.

## Publishing and versioning

Push the repository to GitHub. Users install by `owner/repo`, and can pin:

```bash
pb plugin install owner/pb-mine              # tracks the default branch
pb plugin install owner/pb-mine@v1.2.0       # pinned to a tag
pb plugin install owner/pb-mine --ref abc123 # pinned to a commit
```

A pinned install stays pinned: `pb plugin update` re-resolves the same ref
rather than drifting onto a branch. An unpinned one fast-forwards to the
default branch. Tag your releases and put the pb API version in the README.

Any git URL works too, so a private mirror needs nothing from pb:

```bash
pb plugin install git@github.internal:ops/pb-mine.git
pb plugin install https://gitlab.example/ops/pb-mine.git#v2
```

## Storage paths

```
~/.config/pb/                  or $PB_HOME, or $XDG_CONFIG_HOME/pb
  plugins.json                 what is installed, and at which commit
  plugins/<name>/              the clone - pb owns this; updates reset it
  state/<name>/                your plugin's own data_dir
```

`plugins.json` records installed plugins. A directory absent from that record
is ignored. pb owns the clones, so
`pb plugin update` discards local edits in them - develop against a checkout
of your own with `pb plugin link`, which pb reads in place and never touches
with git.

It is the same directory the [update check](updates.md) keeps its state in,
and `$PB_HOME` moves all of it. [Files pb touches](files.md#writes-in-your-home-directory)
covers every file in there.

## Command reference

```
pb plugin list [--paths]              what is installed, and from where
pb plugin install SOURCE [--ref REF] [--name NAME] [--force] [-y]
pb plugin update [NAME...]            fetch newer commits (default: all)
pb plugin remove NAME                 uninstall
pb plugin enable NAME
pb plugin disable NAME
pb plugin link [PATH] [--name NAME]   develop against a checkout, in place
pb plugin new NAME [--dir DIR] [--owner OWNER]
                                      write a working plugin to start from
pb plugin info NAME                   everything pb knows about one
pb plugin doctor                      load them all and report the failures
pb plugin path                        print the plugin directory
```

The same operations are on the [Plugins tab](../guide/plugins.md), and
[the command line](cli.md) lists every flag.
