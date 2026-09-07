"""`pb plugin new` — a plugin repository that already works.

The template is deliberately a whole small plugin rather than a stub: it uses
most of the hooks, so the fastest way to learn the API is to run it and delete
what you do not want.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .api import API_VERSION
from .manifest import MANIFEST_NAME, NAME_RE, ManifestError, default_module

MANIFEST = """\
# What pb reads before it imports a single line of this plugin.
[plugin]
name = "{name}"
version = "0.1.0"
summary = "{summary}"

# The plugin API this was written against. pb refuses a plugin written for a
# different one rather than half-loading it.
api = {api}

# The module pb imports. Defaults to the name with - and . flattened.
module = "{module}"

# Stylesheets loaded alongside pb's own, so your widgets can be styled.
css = ["{module}/style.tcss"]
"""

INIT = '''\
"""{name} — a pb plugin."""

from __future__ import annotations

from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DataTable, Static

from pb.plugins import CheckResult, Command, KeySpec, Plugin, RunRequest, RunResult, TabSpec


class {cls}Table(DataTable):
    """Bindings live on the widget that owns the verb, as they do in pb, so the
    footer offers them only while this tab has focus."""

    BINDINGS = [Binding("g", "app.{module}_greet", "Greet")]


class {cls}(Plugin):
    """Everything below is optional — delete the hooks you do not need."""

    # --- a tab of your own ------------------------------------------

    def tabs(self):
        yield TabSpec(
            id="tab-{module}",
            title="{title}",
            factory=self._pane,
            focus="#{module}-table",
        )

    def _pane(self):
        """Build the widget that fills the tab. Called once, on mount."""
        return Horizontal(
            {cls}Table(cursor_type="row", zebra_stripes=True, id="{module}-table"),
            VerticalScroll(
                Static("", id="{module}-detail", classes="detail-body"),
                classes="detail",
            ),
            classes="split",
        )

    # --- keys and actions -------------------------------------------

    def keys(self):
        # A binding that works anywhere, as well as the one on the table above.
        yield KeySpec(target="app", key="ctrl+y", action="app.{module}_greet", show=False)

    def actions(self):
        # A name pb already uses would replace the built-in; call
        # self.base_action("run") to wrap it instead of losing it.
        return {{"{module}_greet": self.greet}}

    def greet(self) -> None:
        self.notify(f"{{self.name}} says hello from {{self.repo.root.name}}")

    def commands(self):
        yield Command(title="Greet", callback=self.greet, help="Say hello (ctrl+p)")

    # --- filling the tab in -----------------------------------------

    def activate(self) -> None:
        """Called once, after your tab is mounted. The repo is not read yet."""
        self.app.query_one("#{module}-table", DataTable).add_columns("Playbook", "Roles")

    def reloaded(self) -> None:
        """Called whenever pb has re-read the repo — on start-up, on ctrl+r,
        and after every run. Fill your tab in here."""
        self.refresh_table()

    def refresh_table(self) -> None:
        table = self.app.query_one("#{module}-table", DataTable)
        table.clear()
        for playbook in self.playbooks:
            table.add_row(Text(playbook.name, style="bold"), str(len(playbook.roles)))
        self.app.query_one("#{module}-detail", Static).update(
            Text(f"{{len(self.playbooks)}} playbooks in {{self.repo.root}}", style="dim")
        )

    # --- reacting to the app ----------------------------------------

    def doctor(self):
        """Extra Doctor rows. Runs in a worker thread, so it may shell out."""
        yield CheckResult("{name}", True, f"loaded from {{self.root}}")

    def before_run(self, request: RunRequest) -> None:
        """Inspect, edit or veto a command before it runs.

        request.argv is what will execute and what the user was shown;
        request.env adds environment variables for the child process. Call
        request.veto("why") to stop it.
        """
        request.env.setdefault("ANSIBLE_STDOUT_CALLBACK", "default")

    def after_run(self, result: RunResult) -> None:
        if not result.ok:
            self.notify(f"{{result.label}} exited {{result.exit_code}}", severity="warning")

    def detail(self, pane: str, subject) -> Text | None:
        """Extra text appended to a core detail pane."""
        if pane == "playbook" and subject is not None:
            return Text(
                f"\\n{name}: {{subject.name}} uses {{len(subject.roles)}} roles\\n",
                style="dim",
            )
        return None

    def status_bar(self) -> Text | None:
        return Text(f"  {{self.name}} ✓", style="dim")
'''

STYLE = """\
/* {name} — loaded alongside pb's own stylesheet. Scope your rules to the
   widgets you added; pb's classes (.split, .detail, .detail-body) are
   available so a plugin tab looks like a built-in one. */

#{module}-table {{
    width: 1fr;
    height: 1fr;
}}
"""

README = """\
# {name}

A plugin for [pb](https://github.com/thei1575/ansible-pb).

## Install

```bash
pb plugin install {owner}/{name}
```

## Develop

```bash
pb plugin link .          # pb reads this directory in place
pb plugin doctor          # manifest and import, without starting the TUI
pb                        # restart to pick up an edit
```

## What it does

Describe the tab, keys and checks this adds.
"""

GITIGNORE = """\
__pycache__/
*.py[cod]
.ruff_cache/
.pytest_cache/
"""


@dataclass
class Scaffolded:
    root: Path
    files: list[Path]
    module: str
    git: bool = False


def new(name: str, parent: Path, owner: str = "your-name") -> Scaffolded:
    """Write a working plugin into `parent/name`."""
    if not NAME_RE.match(name):
        raise ManifestError(
            f"{name!r} is not a usable plugin name — lowercase letters, digits, "
            "'-', '_' and '.' only"
        )
    root = (parent / name).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ManifestError(f"{root} already exists and is not empty")

    module = default_module(name)
    # `pb-terraform` -> `Terraform`, for the class name in the template.
    stem = module.removeprefix("pb_") or module
    cls = "".join(part.title() for part in stem.split("_") if part) or "MyPlugin"
    title = stem.replace("_", " ").title()
    summary = f"{title} for pb"

    values = {
        "name": name,
        "module": module,
        "cls": cls,
        "title": title,
        "summary": summary,
        "api": API_VERSION,
        "owner": owner,
    }

    written: list[Path] = []
    for relative, template in (
        (MANIFEST_NAME, MANIFEST),
        (f"{module}/__init__.py", INIT),
        (f"{module}/style.tcss", STYLE),
        ("README.md", README),
        (".gitignore", GITIGNORE),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.format(**values), encoding="utf-8")
        written.append(path)

    return Scaffolded(root=root, files=written, module=module, git=_git_init(root))


def _git_init(root: Path) -> bool:
    """Make it a repository, so publishing it is a push. Best effort."""
    try:
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=str(root),
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True
