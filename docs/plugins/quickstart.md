# Build your first plugin

This tutorial adds a repository summary tab to pb. The finished plugin reads
pb's resolved repository state, renders a Textual table, and refreshes after
each run.

## Create the project

```bash
pb plugin new pb-repo-summary
cd pb-repo-summary
```

The scaffold is a Git repository with this layout:

```text
pb-repo-summary/
├── pb-plugin.toml
├── pb_repo_summary/
│   ├── __init__.py
│   └── style.tcss
├── README.md
└── .gitignore
```

`pb-plugin.toml` is read before Python is imported:

```toml
[plugin]
name = "pb-repo-summary"
version = "0.1.0"
summary = "Repository counts and inventory totals"
api = 1
module = "pb_repo_summary"
css = ["pb_repo_summary/style.tcss"]
```

## Add the tab

Replace `pb_repo_summary/__init__.py` with:

```python
from textual.widgets import DataTable

from pb.plugins import Plugin, TabSpec


class RepoSummary(Plugin):
    def tabs(self):
        yield TabSpec(
            id="tab-repo-summary",
            title="Summary",
            factory=lambda: DataTable(id="repo-summary-table"),
            focus="#repo-summary-table",
            after="tab-status",
        )

    def activate(self) -> None:
        table = self.app.query_one("#repo-summary-table", DataTable)
        table.add_columns("Object", "Count")

    def reloaded(self) -> None:
        table = self.app.query_one("#repo-summary-table", DataTable)
        table.clear()
        table.add_rows(
            [
                ("Playbooks", str(len(self.playbooks))),
                ("Roles", str(len(self.roles))),
                ("Hosts", str(len(self.inventory.hosts))),
                ("Runs", str(len(self.runs))),
            ]
        )


PB_PLUGIN = RepoSummary
```

`tabs()` describes the widget. pb mounts it before `activate()` runs.
`activate()` configures the table once. `reloaded()` fills the rows after pb
has resolved the repository, and runs again after `ctrl+r` and completed runs.

## Link the checkout

```bash
pb plugin link .
pb plugin doctor
pb /path/to/ansible-repo
```

`link` registers the current directory without copying it. Restart pb after a
code or manifest change because plugin modules are imported during startup.
The Plugins tab, opened with <kbd>8</kbd>, identifies linked checkouts and
shows the hooks each plugin implements.

## Add a command

Add `Command` to the import and these methods to `RepoSummary`:

```python
from pb.plugins import Command, Plugin, TabSpec


def commands(self):
    yield Command(
        title="Open repository summary",
        callback=self.open_summary,
        help="Show the plugin tab",
    )

def open_summary(self) -> None:
    self.app.action_tab("tab-repo-summary")
```

Restart pb, press <kbd>ctrl+p</kbd>, and select **Open repository summary**.

## Development loop

```bash
pb plugin doctor
pytest
pb /path/to/ansible-repo
```

Use `pb plugin info pb-repo-summary` when the loaded module, path, API version,
or enabled state is unclear. Continue with the [hook cookbook](hooks.md) for
run policy and UI recipes, then add [headless tests](testing.md) before a
release.
