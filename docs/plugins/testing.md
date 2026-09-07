# Testing and debugging

Plugin tests should cover the manifest, hook behavior, and the mounted Textual
UI separately. Point `PB_HOME` at a temporary directory so tests never read a
developer's installed plugins.

## Test dependencies

Install the plugin and pb in a test environment, then add pytest:

```bash
python -m pip install -e /path/to/ansible-pb
python -m pip install pytest
```

## Isolate pb state

```python
import pytest


@pytest.fixture(autouse=True)
def isolated_pb_home(tmp_path, monkeypatch):
    root = tmp_path / "pb-home"
    monkeypatch.setenv("PB_HOME", str(root))
    monkeypatch.delenv("PB_NO_PLUGINS", raising=False)
    return root
```

## Validate the manifest

```python
from pathlib import Path

from pb.plugins.manifest import load


def test_manifest_targets_current_api():
    manifest = load(Path(__file__).parents[1])
    assert manifest.name == "pb-repo-summary"
    assert manifest.api == 1
    assert manifest.import_name == "pb_repo_summary"
```

`pb plugin doctor` performs the same gate and then imports and constructs the
entry point.

## Test a hook directly

Keep policy in ordinary methods so it can be tested without mounting Textual.

```python
from pb.plugins import RunRequest
from pb_repo_summary import RepoSummary


def test_check_mode_enables_diff():
    plugin = RepoSummary()
    request = RunRequest(
        argv=["ansible-playbook", "playbooks/site.yml", "--check"],
        label="Check site.yml",
        mode="check",
    )

    plugin.before_run(request)

    assert request.argv[-1] == "--diff"
    assert not request.vetoed
```

## Test loading through the store

This catches manifest, module path, entry-point, and constructor failures.

```python
from pathlib import Path

from pb.plugins import load_all
from pb.plugins.manage import link
from pb.plugins.store import Store


def test_plugin_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("PB_HOME", str(tmp_path / "pb-home"))
    plugin_root = Path(__file__).parents[1]
    store = Store()
    link(store, plugin_root)

    loaded = load_all(store)

    assert loaded.failures == []
    assert [plugin.name for plugin in loaded.plugins] == ["pb-repo-summary"]
```

## Test the mounted app

Textual's test pilot verifies that a tab exists and accepts focus. Build a
small Ansible fixture repository for `PbApp` to discover.

```python
import asyncio
from pathlib import Path

from textual.widgets import DataTable, TabPane

from pb.app import PbApp
from pb.plugins.manage import link
from pb.plugins.store import Store


def test_summary_tab(repo_root, tmp_path, monkeypatch):
    monkeypatch.setenv("PB_HOME", str(tmp_path / "pb-home"))
    link(Store(), Path(__file__).parents[1])
    app = PbApp(repo_root)

    async def scenario():
        async with app.run_test() as pilot:
            for _ in range(100):
                await pilot.pause()
                if app.playbooks:
                    break

            pane = app.query_one("#tab-repo-summary", TabPane)
            table = app.query_one("#repo-summary-table", DataTable)
            assert pane.id == "tab-repo-summary"
            assert table.row_count == 4

    asyncio.run(scenario())
```

The plugin must be linked before `PbApp` is constructed because the loader
runs during initialization.

## Loader failure stages

| Stage | Inspect |
|---|---|
| `manifest` | TOML syntax, API number, path containment, recorded directory |
| `import` | module name, `python_path`, import-time exception, dependency |
| `entry-point` | `PB_PLUGIN` value or module-defined subclasses |
| `construct` | plugin constructor and class initialization |
| hook name | traceback from an active plugin disabled during the session |

Run these commands against the same `PB_HOME` used by the application:

```bash
pb plugin info pb-repo-summary
pb plugin doctor
pb plugin list --paths
```

Use `PB_NO_PLUGINS=1 pb /path/to/repo` to confirm whether a failure depends on
plugin code.

## Test checklist

- Parse the production `pb-plugin.toml`.
- Load the linked checkout through `Store` and `load_all()`.
- Exercise argument and environment changes for every supported run mode.
- Verify veto reasons and empty-state handling.
- Mount each contributed tab in a headless `PbApp` test.
- Press contributed keys with the intended target focused.
- Raise once from each critical hook and inspect the resulting Doctor failure.
- Run `pb plugin doctor` before tagging a release.
