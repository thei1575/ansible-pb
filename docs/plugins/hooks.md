# Hook cookbook

Each recipe is independent. Import the records used by the hooks you keep.

```python
from pb.plugins import CheckResult, Command, KeySpec, Plugin, RunRequest, RunResult, TabSpec
```

## Bind a key to a core table

Bindings attached to a table appear in the footer while that table has focus.
Use `target="app"` for a global binding.

```python
def keys(self):
    yield KeySpec(
        target="hosts",
        key="D",
        action="app.show_drift",
        description="Drift",
    )

def actions(self):
    return {"show_drift": self.show_drift}

def show_drift(self) -> None:
    host = self.app.host
    if host is not None:
        self.view(f"Drift: {host.name}", self.report_for(host))
```

Action strings use Textual namespaces. An action installed on the app is
addressed as `app.show_drift`.

## Wrap a built-in action

This wrapper requires a change-ticket environment variable before a playbook
can run, then delegates to the previous `run` action.

```python
import os


def actions(self):
    return {"run": self.run_with_ticket}

def run_with_ticket(self):
    if not os.environ.get("CHANGE_TICKET"):
        self.notify("CHANGE_TICKET is required", severity="error")
        return None
    base = self.base_action("run")
    return base() if base is not None else None
```

The [API reference](../reference/writing-plugins.md#keys-and-actions-including-replacing-pbs-own)
lists replaceable built-in actions by tab.

## Enforce run policy

`before_run()` sees pb commands and commands launched by plugins. Changes are
applied before the confirmation screen.

```python
def before_run(self, request: RunRequest) -> None:
    if request.mode in {"run", "repeat"} and self.production_is_frozen():
        request.veto("production change freeze is active")
        return

    if request.mode == "check" and "--diff" not in request.argv:
        request.argv.append("--diff")

    request.env["ANSIBLE_CALLBACKS_ENABLED"] = "profile_tasks"
```

Keep mutations idempotent. A repeated History run passes through the hook
again with `mode="repeat"`.

## Record completed runs

`after_run()` is suitable for local audit indexes and asynchronous delivery.
It runs on the UI thread, so file and network work should be moved to a worker.

```python
import json


def after_run(self, result: RunResult) -> None:
    payload = {
        "label": result.label,
        "exit_code": result.exit_code,
        "duration": result.duration,
        "recap": result.recap,
    }
    self.app.run_worker(
        lambda: self.write_audit_event(payload),
        thread=True,
        name=f"{self.name}-audit",
    )

def write_audit_event(self, payload: dict) -> None:
    self.data_dir.mkdir(parents=True, exist_ok=True)
    path = self.data_dir / "runs.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload) + "\n")
```

## Add Doctor checks

Doctor hooks already run in a worker thread and may use `meta.capture()`.

```python
from pb import meta


def doctor(self):
    code, output = meta.capture(["terraform", "version"], self.repo.root)
    first_line = output.splitlines()[0] if output else "terraform was not found"
    yield CheckResult("terraform", code == 0, first_line)

    config = self.repo.root / "drift-policy.toml"
    yield CheckResult("drift policy", config.is_file(), str(config))
```

Use `ok=None` for a warning that should remain visible without failing the
check set.

## Extend detail panes

Return a string or Rich `Text`. Return `None` for panes the plugin does not
extend.

```python
from rich.text import Text


def detail(self, pane: str, subject):
    if pane != "host":
        return None
    result = self.last_result.get(subject.name, "not checked")
    color = "green" if result == "clean" else "yellow"
    return Text(f"\npolicy: {result}\n", style=color)
```

Pane names are `playbook`, `host`, `role`, `vault`, `status`, and `history`.

## Publish status

```python
def status_bar(self):
    count = len(self.drifted_hosts)
    return f"  drift {count}" if count else "  drift clean"
```

The value is collected during repaint. Use cached state and keep the hook
cheap.

## Launch a recorded command

```python
def scan_selected(self) -> None:
    host = self.app.host
    if host is None:
        return
    self.launch(
        ["driftctl", "scan", "--host", host.name],
        label=f"Drift scan: {host.name}",
        mode="ad-hoc",
    )
```

The command uses pb's full-screen runner, passes through `before_run()`, and is
written to History. Use `self.view(title, body, lexer)` for output already in
memory and `self.notify()` for short feedback.

## Add palette commands

```python
def commands(self):
    yield Command(
        title="Clear drift cache",
        callback=self.clear_cache,
        help="Remove cached scan results",
    )

def clear_cache(self) -> None:
    self.last_result.clear()
    self.reload()
```

Command callbacks may return an awaitable. pb guards both synchronous and
asynchronous callbacks and disables a plugin whose callback raises.
