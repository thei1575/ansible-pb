# Architecture and lifecycle

Plugins execute in the pb process and contribute directly to its Textual
application. The manifest provides an import gate. The Python API supplies
typed contribution records and lifecycle hooks.

## Load sequence

pb processes enabled plugins in installation order.

1. Read the record from `plugins.json`.
2. Locate the installed checkout or linked working directory.
3. Parse `pb-plugin.toml` and validate paths and API compatibility.
4. Reserve the declared Python module name.
5. Add each `python_path` entry to `sys.path` and import the module.
6. Resolve `PB_PLUGIN`, or scan for `Plugin` subclasses defined by the module.
7. Construct the plugin instances and attach manifest metadata.
8. Mount tabs, install actions and keys, then call `activate()`.
9. Load the repository and call `reloaded()`.

Manifest validation happens before import. A plugin declaring an unsupported
API version cannot execute module-level code.

## Entry-point discovery

The loader accepts an explicit class, instance, or sequence:

```python
PB_PLUGIN = MyPlugin
PB_PLUGIN = MyPlugin()
PB_PLUGIN = [InventoryPlugin, AuditPlugin]
```

Without `PB_PLUGIN`, the loader constructs every `Plugin` subclass defined in
the declared module. Imported subclasses are ignored during this scan. An
explicit entry point is useful when a module contains shared base classes.

## Hook timing

| Hook | Timing | Repeats | Thread |
|---|---|---:|---|
| `tabs()` | application setup | no | UI |
| `actions()` | application setup | no | UI |
| `keys()` | application setup | no | UI |
| `activate()` | after contributions are installed | no | UI |
| `reloaded()` | after repository discovery and repaint | yes | UI |
| `doctor()` | when checks are collected | yes | worker |
| `before_run()` | before confirmation and execution | yes | UI |
| `after_run()` | after a streamed run is recorded | yes | UI |
| `detail()` | while a core detail pane renders | yes | UI |
| `status_bar()` | while the status strip renders | yes | UI |
| `deactivate()` | clean application shutdown | no | UI |

Only `doctor()` is run in a worker thread. UI hooks should schedule slow work
with `self.app.run_worker(..., thread=True)` and return promptly. Commands
started through `self.launch()` use pb's run screen and history pipeline.

## Action resolution

Actions are installed in plugin order. A later plugin may replace an action
registered by pb or an earlier plugin. `base_action(name)` returns the action
that was present immediately before the current plugin replaced it.

```python
def actions(self):
    return {"reload": self.reload_with_cache_clear}

def reload_with_cache_clear(self):
    self.cache.clear()
    base = self.base_action("reload")
    if base is not None:
        return base()
```

This creates a chain when several plugins wrap the same action. Installation
order determines the outermost wrapper.

## Run pipeline

`before_run()` receives a mutable `RunRequest`. Plugins may append arguments,
set child-process environment variables, or veto execution. The resulting
command is displayed after all accepted changes. Processing stops at the first
veto and records the plugin name in `vetoed_by`.

Streamed commands produce a `RunResult` after history has been written.
Commands handed to an interactive terminal, including SSH and vault editing,
do not produce `after_run()` events.

## State ownership

The loader assigns two paths:

| Property | Owner | Expected contents |
|---|---|---|
| `self.root` | plugin package | imported code, static data, TCSS |
| `self.data_dir` | plugin | caches, indexes, plugin configuration |

Create `data_dir` before writing:

```python
self.data_dir.mkdir(parents=True, exist_ok=True)
cache = self.data_dir / "inventory-index.json"
```

Installed checkouts may be replaced during updates. Persistent data belongs in
`data_dir`.

## Failure handling

Import and construction failures are recorded with a stage and traceback.
When an active hook raises, pb disables that plugin for the current session,
removes its tabs, restores replaced actions, adds a Doctor failure, and keeps
other plugins active. `pb plugin doctor` prints loader failures without
starting the TUI.

## Process boundary

Plugin code has the same operating-system permissions as pb. It can access the
repository, environment, vault password files, network, and subprocesses.
There is no sandbox or separate interpreter. Review third-party plugin code
and its exact installed commit before enabling it.
