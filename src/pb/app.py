"""pb — a console for driving an Ansible repo.

Tabs mirror the repo's own structure: playbooks you run, the inventory they
run against, the roles they compose, the vaults that hold the secrets, and a
doctor that checks the whole thing is wired up.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane

from . import __version__, history, hoststatus, meta, runner, update
from .run import RunScreen
from .widgets import AskText, Confirm, PickMany, PickOne, UpdatePrompt, Viewer

# A TabPane only stays active while focus is inside it: a focused widget in
# another pane posts TabPane.Focused and yanks the tab back. So switching tabs
# means moving focus, not just setting `active`.
TAB_TABLES = {
    "tab-playbooks": "#playbooks",
    "tab-inventory": "#hosts",
    "tab-status": "#status",
    "tab-roles": "#roles",
    "tab-vault": "#vaults",
    "tab-history": "#history",
    "tab-doctor": "#doctor",
}

DIRTY = "● "     # marks a file that differs from HEAD
CLEAN = "  "

MODE_LABELS = {
    "run": ("apply", "green"),
    "check": ("dry run", "cyan"),
    "syntax": ("syntax check", "blue"),
}


@dataclass
class RunOptions:
    """The --tags/--limit/-v knobs, shared by every playbook action."""

    tags: list[str] = field(default_factory=list)
    limit: str = ""
    extra: str = ""
    verbosity: int = 0
    diff: bool = False

    def clear(self) -> None:
        self.tags, self.limit, self.extra = [], "", ""
        self.verbosity, self.diff = 0, False

    def as_args(self) -> list[str]:
        args: list[str] = []
        if self.tags:
            args += ["--tags", ",".join(self.tags)]
        if self.limit:
            args += ["--limit", self.limit]
        if self.diff:
            args.append("--diff")
        if self.verbosity:
            args.append("-" + "v" * self.verbosity)
        if self.extra:
            args += shlex.split(self.extra)
        return args

    def render(self) -> Text:
        text = Text()
        def part(label: str, value: str, on: bool) -> None:
            text.append(f" {label} ", style="bold bright_cyan" if on else "dim")
            text.append(f"{value}  ", style="bold" if on else "dim")

        part("tags", ",".join(self.tags) or "all", bool(self.tags))
        part("limit", self.limit or "all", bool(self.limit))
        part("diff", "on" if self.diff else "off", self.diff)
        part("-v", str(self.verbosity) or "0", bool(self.verbosity))
        part("extra", self.extra or "—", bool(self.extra))
        text.append(" t·l·d·v·e edit  x clear", style="dim")
        return text


# --- tables, each with its own verbs ---------------------------------


# Bindings live on the table that owns the verb, so the footer only offers
# what the focused tab can do. The actions themselves live on the app, hence
# the explicit `app.` namespace — a widget binding does not bubble on its own.
class PlaybookTable(DataTable):
    BINDINGS = [
        Binding("r", "app.run", "Run"),
        Binding("c", "app.check", "Dry run"),
        Binding("s", "app.syntax", "Syntax"),
        Binding("t", "app.tags", "Tags"),
        Binding("l", "app.limit", "Limit"),
        Binding("d", "app.diff", "Diff"),
        Binding("v", "app.verbosity", "-v"),
        Binding("e", "app.extra", "Extra args"),
        Binding("x", "app.clear", "Clear opts"),
        Binding("o", "app.open", "Open file"),
    ]


class HostTable(DataTable):
    BINDINGS = [
        Binding("p", "app.ping", "Ping"),
        Binding("f", "app.facts", "Facts"),
        Binding("i", "app.inspect", "Vars"),
        Binding("s", "app.ssh", "SSH"),
        Binding("R", "app.reveal", "Reveal secrets"),
    ]


class RoleTable(DataTable):
    BINDINGS = [
        Binding("d", "app.defaults", "Defaults"),
        Binding("t", "app.tasks", "Tasks"),
    ]


class VaultTable(DataTable):
    BINDINGS = [
        Binding("v", "app.view", "View"),
        Binding("e", "app.edit", "Edit"),
        Binding("n", "app.new", "New group"),
        Binding("k", "app.rekey", "Rekey all"),
    ]


class StatusTable(DataTable):
    BINDINGS = [
        Binding("r", "app.refresh_status", "Refresh"),
        Binding("s", "app.ssh", "SSH"),
    ]


class HistoryTable(DataTable):
    BINDINGS = [
        Binding("o", "app.show_log", "Open log"),
        Binding("a", "app.rerun", "Run again"),
    ]


class DoctorTable(DataTable):
    BINDINGS = [Binding("r", "app.recheck", "Re-check")]


# --- the app ----------------------------------------------------------


class PbApp(App[None]):
    CSS_PATH = "pb.tcss"
    TITLE = "pb"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
        Binding("ctrl+r", "reload", "Reload"),
        Binding("ctrl+g", "changes", "Changes"),
        Binding("ctrl+u", "check_update", "Update"),
        Binding("1", "tab('tab-playbooks')", "", show=False),
        Binding("2", "tab('tab-inventory')", "", show=False),
        Binding("3", "tab('tab-status')", "", show=False),
        Binding("4", "tab('tab-roles')", "", show=False),
        Binding("5", "tab('tab-vault')", "", show=False),
        Binding("6", "tab('tab-history')", "", show=False),
        Binding("7", "tab('tab-doctor')", "", show=False),
    ]

    def __init__(
        self, root: Path, inventory: str | None = None, check_updates: bool = True
    ) -> None:
        super().__init__()
        self.repo = meta.Repo.discover(root, inventory)
        self.check_updates = check_updates
        self.options = RunOptions()
        self.playbooks: list[meta.Playbook] = []
        self.inventory = meta.Inventory()
        self.roles: list[meta.Role] = []
        self.vaults: list[meta.Vault] = []
        self.reveal_secrets = False
        self.changed: set[str] = set()
        self.host_status: dict[str, hoststatus.HostStatus] = {}
        self.runs: list[history.Run] = []
        # Set once a check has found something newer, so Doctor can say so
        # without going back to the network.
        self.update_release: update.Release | None = None
        self.sub_title = str(root)

    # --- layout ------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("", id="statusbar")
        with TabbedContent(initial="tab-playbooks"):
            with TabPane("Playbooks", id="tab-playbooks"):
                with Horizontal(classes="split"):
                    yield PlaybookTable(cursor_type="row", zebra_stripes=True, id="playbooks")
                    with VerticalScroll(classes="detail"):
                        yield Static("", id="playbook-detail", classes="detail-body")
                yield Static("", id="options")
            with TabPane("Inventory", id="tab-inventory"):
                with Horizontal(classes="split"):
                    yield HostTable(cursor_type="row", zebra_stripes=True, id="hosts")
                    with VerticalScroll(classes="detail"):
                        yield Static("", id="host-detail", classes="detail-body")
            with TabPane("Status", id="tab-status"):
                with Horizontal(classes="split"):
                    yield StatusTable(cursor_type="row", zebra_stripes=True, id="status")
                    with VerticalScroll(classes="detail"):
                        yield Static("", id="status-detail", classes="detail-body")
            with TabPane("Roles", id="tab-roles"):
                with Horizontal(classes="split"):
                    yield RoleTable(cursor_type="row", zebra_stripes=True, id="roles")
                    with VerticalScroll(classes="detail"):
                        yield Static("", id="role-detail", classes="detail-body")
            with TabPane("Vault", id="tab-vault"):
                with Horizontal(classes="split"):
                    yield VaultTable(cursor_type="row", zebra_stripes=True, id="vaults")
                    with VerticalScroll(classes="detail"):
                        yield Static("", id="vault-detail", classes="detail-body")
            with TabPane("History", id="tab-history"):
                with Horizontal(classes="split"):
                    yield HistoryTable(cursor_type="row", zebra_stripes=True, id="history")
                    with VerticalScroll(classes="detail"):
                        yield Static("", id="history-detail", classes="detail-body")
            with TabPane("Doctor", id="tab-doctor"):
                yield DoctorTable(cursor_type="row", zebra_stripes=True, id="doctor")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#playbooks", DataTable).add_columns(
            "Playbook", "Kind", "Targets", "Roles", "What it does"
        )
        self.query_one("#hosts", DataTable).add_columns("Host", "Address", "Groups")
        self.query_one("#roles", DataTable).add_columns("Role", "Tasks", "Contains", "Used by")
        self.query_one("#vaults", DataTable).add_columns("Group", "State", "Size", "Path")
        self.query_one("#status", DataTable).add_columns(
            "Host", "State", "Uptime", "Load", "Disk", "Memory", "Notes"
        )
        self.query_one("#history", DataTable).add_columns(
            "When", "What", "Result", "Took", "Recap"
        )
        self.query_one("#doctor", DataTable).add_columns("Check", "Status", "Detail")
        self._render_options()
        self.query_one("#playbooks", DataTable).focus()
        self.reload()
        if self.check_updates:
            self._check_for_update()

    def action_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab
        self._focus_pane(tab)

    def _focus_pane(self, pane_id: str | None) -> None:
        table = TAB_TABLES.get(pane_id or "")
        if table:
            self.query_one(table, DataTable).focus()

    # --- loading ------------------------------------------------------

    @work(thread=True, exclusive=True)
    def reload(self) -> None:
        playbooks = meta.discover_playbooks(self.repo)
        roles = meta.discover_roles(self.repo, playbooks)
        vaults = meta.discover_vaults(self.repo)
        branch, dirty = meta.git_status(self.repo)
        changed = meta.changed_paths(self.repo)
        runs = history.load(self.repo)
        inventory = meta.load_inventory(self.repo)
        self.call_from_thread(
            self._apply_load, playbooks, roles, vaults, inventory, branch, dirty, changed, runs
        )

    def _apply_load(
        self, playbooks, roles, vaults, inventory, branch, dirty, changed, runs
    ) -> None:
        self.playbooks, self.roles, self.vaults = playbooks, roles, vaults
        self.inventory = inventory
        self.changed, self.runs = changed, runs

        table = self.query_one("#playbooks", DataTable)
        table.clear()
        for pb in playbooks:
            kind_style = {"aggregate": "magenta", "interactive": "yellow"}.get(pb.kind, "cyan")
            dirty_pb = self._is_dirty(pb.path)
            table.add_row(
                Text((DIRTY if dirty_pb else CLEAN) + pb.name,
                     style="bold yellow" if dirty_pb else "bold"),
                Text(pb.kind, style=kind_style),
                ", ".join(pb.targets) or ("→ " + ", ".join(pb.imports) if pb.imports else "—"),
                str(len(pb.roles)) if pb.roles else "—",
                Text(_short(pb.summary), style="dim"),
                key=pb.name,
            )

        hosts = self.query_one("#hosts", DataTable)
        hosts.clear()
        for host in inventory.hosts:
            hosts.add_row(
                Text(host.name, style="bold"),
                host.address or "—",
                Text(", ".join(host.groups), style="dim"),
                key=host.name,
            )

        role_table = self.query_one("#roles", DataTable)
        role_table.clear()
        for role in roles:
            dirty_role = any(p.startswith(f"roles/{role.name}/") for p in self.changed)
            role_table.add_row(
                Text((DIRTY if dirty_role else CLEAN) + role.name,
                     style="bold yellow" if dirty_role else "bold"),
                str(role.tasks),
                Text(", ".join(role.parts) or "—", style="dim"),
                Text(", ".join(role.used_by) or "unused", style="dim" if role.used_by else "red"),
                key=role.name,
            )

        vault_table = self.query_one("#vaults", DataTable)
        vault_table.clear()
        for vault in vaults:
            vault_table.add_row(
                Text(vault.group, style="bold"),
                Text("encrypted", style="green")
                if vault.encrypted
                else Text("PLAINTEXT", style="bold red"),
                f"{vault.size}b",
                Text(str(vault.path.relative_to(self.repo.root)), style="dim"),
                key=vault.group,
            )

        self._render_history_table()
        self._render_status_table()
        self._render_statusbar(branch, dirty)
        self._render_playbook_detail()
        self._render_status_detail()
        self._render_run_detail()
        self._render_host_detail()
        self._render_role_detail()
        self._render_vault_detail()
        if inventory.error:
            self.notify(f"inventory: {inventory.error}", severity="error", timeout=10)
        elif inventory.warning:
            self.notify(f"inventory: {inventory.warning}", severity="warning", timeout=10)

    def _render_statusbar(self, branch: str, dirty: int) -> None:
        text = Text()
        text.append(" pb ", style="bold white on dark_blue")
        text.append(f" {self.repo.root.name} ", style="bold")
        if branch:
            text.append(f"⎇ {branch}", style="cyan")
            text.append(f" ✎{dirty}" if dirty else " ✓", style="yellow" if dirty else "green")
        text.append(
            f"  ·  {len(self.playbooks)} playbooks  ·  {len(self.inventory.hosts)} hosts"
            f"  ·  {len(self.roles)} roles  ·  {len(self.vaults)} vaults",
            style="dim",
        )
        vault_pass = self.repo.vault_pass_file
        if not vault_pass.exists():
            text.append("   .vault_pass MISSING", style="bold red")
        self.query_one("#statusbar", Static).update(text)

    # --- current selection helpers -------------------------------------

    def _current(self, table_id: str, items: list, attr: str):
        table = self.query_one(f"#{table_id}", DataTable)
        if table.row_count == 0:
            return None
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        return next((i for i in items if getattr(i, attr) == key), None)

    def _is_dirty(self, path: Path) -> bool:
        return str(path.relative_to(self.repo.root)) in self.changed

    @property
    def playbook(self) -> meta.Playbook | None:
        return self._current("playbooks", self.playbooks, "name")

    @property
    def host(self) -> meta.Host | None:
        return self._current("hosts", self.inventory.hosts, "name")

    @property
    def role(self) -> meta.Role | None:
        return self._current("roles", self.roles, "name")

    @property
    def vault(self) -> meta.Vault | None:
        return self._current("vaults", self.vaults, "group")

    @property
    def status_host(self) -> meta.Host | None:
        return self._current("status", self.inventory.hosts, "name")

    @property
    def run_record(self) -> history.Run | None:
        return self._current("history", self.runs, "id")

    @on(DataTable.RowHighlighted)
    def _selection_moved(self, event: DataTable.RowHighlighted) -> None:
        which = event.data_table.id
        if which == "playbooks":
            self._render_playbook_detail()
        elif which == "hosts":
            self._render_host_detail()
        elif which == "roles":
            self._render_role_detail()
        elif which == "vaults":
            self._render_vault_detail()
        elif which == "status":
            self._render_status_detail()
        elif which == "history":
            self._render_run_detail()

    # --- detail panes ---------------------------------------------------

    def _render_options(self) -> None:
        self.query_one("#options", Static).update(self.options.render())

    def _render_playbook_detail(self) -> None:
        pb = self.playbook
        target = self.query_one("#playbook-detail", Static)
        if pb is None:
            target.update(Text("no playbooks found", style="dim"))
            return
        text = Text()
        text.append(f"{pb.name}\n", style="bold bright_cyan")
        text.append(f"{pb.path.relative_to(self.repo.root)}\n\n", style="dim")
        if pb.summary:
            text.append(pb.summary + "\n\n")
        if pb.imports:
            text.append("imports\n", style="bold")
            for name in pb.imports:
                text.append(f"  → {name}\n", style="magenta")
            text.append("\n")
        if pb.targets:
            text.append("targets\n", style="bold")
            for host in pb.targets:
                members = self.inventory.groups.get(host)
                suffix = f"  ({', '.join(members)})" if members else ""
                text.append(f"  {host}{suffix}\n", style="cyan")
            text.append("\n")
        if pb.roles:
            text.append("roles\n", style="bold")
            for role in pb.roles:
                text.append(f"  {role}\n")
            text.append("\n")
        if pb.interactive:
            text.append("prompts for input — runs in the foreground\n\n", style="yellow")
        text.append("would run\n", style="bold")
        text.append(_wrap(" ".join(shlex.quote(a) for a in self._argv(pb, "run"))), style="green")
        target.update(text)

    def _render_host_detail(self) -> None:
        host = self.host
        target = self.query_one("#host-detail", Static)
        if host is None:
            why = self.inventory.error or self.inventory.warning or "no hosts"
            target.update(
                Text(f"{why}\n\n{self.repo.rel(self.repo.inventory)}\n", style="dim")
            )
            return
        text = Text()
        text.append(f"{host.name}\n", style="bold bright_cyan")
        text.append(f"{host.address}\n\n", style="dim")
        text.append("groups\n", style="bold")
        for group in host.groups:
            text.append(f"  {group}\n", style="cyan")
        text.append("\nkey vars", style="bold")
        text.append(
            "   (secrets revealed — R hides)\n" if self.reveal_secrets
            else "   (secrets masked — R reveals)\n",
            style="yellow" if self.reveal_secrets else "dim",
        )
        values = host.vars if self.reveal_secrets else meta.redact(host.vars)
        interesting = [
            k for k in sorted(values)
            if not k.startswith("ansible_") or k in ("ansible_host", "ansible_user")
        ]
        for key in interesting[:24]:
            raw = str(values[key])
            value = raw if len(raw) <= 44 else raw[:43] + "…"
            hidden = raw == meta.MASK
            revealed = self.reveal_secrets and meta.is_secret(key)
            text.append(f"  {key}", style="dim")
            text.append(
                f" = {value}\n",
                style="red" if hidden else "yellow" if revealed else "",
            )
        if len(interesting) > 24:
            text.append(f"  … {len(interesting) - 24} more — press i\n", style="dim")
        target.update(text)

    def _render_role_detail(self) -> None:
        role = self.role
        target = self.query_one("#role-detail", Static)
        if role is None:
            target.update(Text("no roles", style="dim"))
            return
        text = Text()
        text.append(f"{role.name}\n", style="bold bright_cyan")
        text.append(f"{role.path.relative_to(self.repo.root)}\n\n", style="dim")
        text.append("task files\n", style="bold")
        for path in sorted(role.path.glob("tasks/*.yml")):
            text.append(f"  {path.name}\n")
        text.append("\ncontains\n", style="bold")
        text.append("  " + (", ".join(role.parts) or "tasks only") + "\n")
        text.append("\nused by\n", style="bold")
        for name in role.used_by or ["(no playbook references this role)"]:
            text.append(f"  {name}\n", style="cyan" if role.used_by else "red")
        target.update(text)

    def _render_vault_detail(self) -> None:
        vault = self.vault
        target = self.query_one("#vault-detail", Static)
        if vault is None:
            target.update(Text("no vaults", style="dim"))
            return
        text = Text()
        text.append(f"{vault.group}\n", style="bold bright_cyan")
        text.append(f"{vault.path.relative_to(self.repo.root)}\n\n", style="dim")
        text.append("Secrets for this group only, so a service carries just what\n", style="dim")
        text.append("it needs. Decrypted with .vault_pass.\n\n", style="dim")
        text.append("v", style="bold")
        text.append("  view decrypted (on screen)\n")
        text.append("e", style="bold")
        text.append("  edit in $EDITOR\n")
        text.append("n", style="bold")
        text.append("  create a vault for a new group\n")
        text.append("k", style="bold")
        text.append("  rekey every vault\n")
        target.update(text)

    def _render_status_table(self) -> None:
        table = self.query_one("#status", DataTable)
        table.clear()
        blank = ("—", "—", "—", "—")
        for host in self.inventory.hosts:
            probe = self.host_status.get(host.name)
            name = Text(host.name, style="bold")

            if probe is None:
                table.add_row(name, Text("? unknown", style="dim"), *blank,
                              Text("press r to probe", style="dim"), key=host.name)
                continue
            if probe.local:
                table.add_row(name, Text("— local", style="dim"), *blank,
                              Text("not probed", style="dim"), key=host.name)
                continue
            if not probe.reachable:
                table.add_row(name, Text("✘ unreachable", style="bold red"), *blank,
                              Text(probe.error, style="red"), key=host.name)
                continue

            state = (Text("✔ healthy", style="bold green") if probe.healthy
                     else Text("! degraded", style="bold yellow"))
            table.add_row(
                name,
                state,
                _short_uptime(probe.get("uptime")),
                probe.get("load"),
                Text(probe.get("disk"), style="red" if probe.disk_pct >= 90 else ""),
                probe.get("mem"),
                _notes(probe),
                key=host.name,
            )

    def _render_status_detail(self) -> None:
        host = self.status_host
        target = self.query_one("#status-detail", Static)
        if host is None:
            target.update(Text("no hosts", style="dim"))
            return
        probe = self.host_status.get(host.name)
        text = Text()
        text.append(f"{host.name}\n", style="bold bright_cyan")
        text.append(f"{host.address}\n\n", style="dim")
        if probe is None:
            text.append("not probed yet — press r\n", style="dim")
            target.update(text)
            return
        if probe.local or not probe.reachable:
            text.append(probe.error or "unreachable", style="dim" if probe.local else "bold red")
            target.update(text)
            return

        text.append(f"{probe.get('os')}\n", style="bold")
        text.append(f"kernel {probe.get('kernel')}\n\n", style="dim")
        for label, key in (("uptime", "uptime"), ("load", "load"), ("disk /", "disk"),
                           ("memory", "mem"), ("services", "services")):
            text.append(f"  {label:10}", style="dim")
            text.append(f"{probe.get(key)}\n")

        text.append("\nhousekeeping\n", style="bold")
        updates = probe.get("updates", "0")
        text.append("  updates   ", style="dim")
        text.append(f"{updates} pending\n", style="cyan" if updates not in ("0", "—") else "")
        text.append("  reboot    ", style="dim")
        reboot = probe.get("reboot")
        text.append(f"{reboot}\n", style="yellow" if reboot == "yes" else "green")
        failed = probe.failed_units
        text.append("  failed    ", style="dim")
        text.append(", ".join(failed) + "\n" if failed else "none\n",
                    style="bold red" if failed else "green")

        if probe.containers:
            text.append("\ncontainers\n", style="bold")
            for name, state in probe.containers:
                up = state.lower().startswith("up")
                text.append(f"  {name}\n", style="" if up else "red")
                text.append(f"    {state}\n", style="dim")
        if probe.certs:
            text.append("\ncertificates\n", style="bold")
            for name, expiry in probe.certs:
                text.append(f"  {name}\n")
                text.append(f"    expires {expiry}\n", style="dim")
        target.update(text)

    def _render_history_table(self) -> None:
        table = self.query_one("#history", DataTable)
        table.clear()
        for run in self.runs:
            result = (Text("✔ ok", style="bold green") if run.ok
                      else Text(f"✘ {run.exit_code}", style="bold red"))
            table.add_row(
                Text(run.when, style="dim"),
                Text(run.label, style="bold" if run.applied else ""),
                result,
                f"{run.duration:.0f}s",
                Text(run.recap_summary() or "—", style="dim"),
                key=run.id,
            )

    def _render_run_detail(self) -> None:
        run = self.run_record
        target = self.query_one("#history-detail", Static)
        if run is None:
            target.update(Text("nothing has been run through pb yet", style="dim"))
            return
        text = Text()
        text.append(f"{run.label}\n", style="bold bright_cyan")
        text.append(f"{run.when}   {run.duration:.1f}s\n\n", style="dim")
        text.append("applied\n" if run.applied else "dry run / check only\n",
                    style="bold yellow" if run.applied else "dim")
        text.append("\ncommand\n", style="bold")
        text.append(_wrap(" ".join(shlex.quote(a) for a in run.argv)) + "\n", style="green")
        text.append("\nat commit\n", style="bold")
        text.append(f"  {run.git_sha or '?'} on {run.git_branch or '?'}"
                    + (f", {run.git_dirty} uncommitted\n" if run.git_dirty else "\n"),
                    style="yellow" if run.git_dirty else "")
        if run.recap:
            text.append("\nrecap\n", style="bold")
            for host, counts in run.recap.items():
                text.append(f"  {host}", style="bold")
                for key, style in (("ok", "green"), ("changed", "yellow"),
                                   ("failed", "red"), ("unreachable", "red")):
                    if counts.get(key):
                        text.append(f" {key}={counts[key]}", style=style)
                text.append("\n")
        text.append("\no", style="bold")
        text.append("  open the saved output\n")
        text.append("a", style="bold")
        text.append("  run the same command again\n")
        target.update(text)

    # --- building and launching commands ---------------------------------

    def _argv(self, pb: meta.Playbook, mode: str) -> list[str]:
        argv = ["ansible-playbook", self.repo.rel(pb.path), *self.repo.inventory_args]
        if mode == "check":
            argv.append("--check")
        elif mode == "syntax":
            argv.append("--syntax-check")
        options = self.options.as_args()
        # A dry run without --diff tells you almost nothing, so imply it
        # rather than making the toggle a prerequisite.
        if mode == "check" and "--diff" not in options:
            argv.append("--diff")
        return argv + options

    def _launch(self, argv: list[str], label: str) -> None:
        def done(_code: int | None) -> None:
            # A finished run is new history, and an apply may have changed the
            # working tree, so refresh rather than leave the tabs stale.
            self.reload()

        self.push_screen(RunScreen(argv, self.repo, label), done)

    def _foreground(self, argv: list[str]) -> None:
        """Drop out of the TUI for anything that needs a real terminal."""
        with self.suspend():
            os.system("clear")
            print("$ " + " ".join(shlex.quote(a) for a in argv) + "\n")
            try:
                subprocess.run(argv, cwd=str(self.repo.root))
            except FileNotFoundError as exc:
                print(f"pb: {exc}")
            input("\n-- press enter to return to pb --")
        self.reload()

    # --- playbook actions -------------------------------------------------

    def _playbook_action(self, mode: str) -> None:
        pb = self.playbook
        if pb is None:
            return
        argv = self._argv(pb, mode)
        label, _ = MODE_LABELS[mode]
        if pb.interactive and mode == "run":
            self._foreground(argv)
            return

        def go(ok: bool | None) -> None:
            if ok:
                self._launch(argv, f"{pb.name} ({label})")

        if mode == "run":
            # Patterns are not an answer to "what am I about to change", so ask
            # ansible for the real host list before showing the confirmation.
            self.notify("resolving which hosts this would touch…")
            self._confirm_apply(pb, argv, go)
        else:
            go(True)

    @work(thread=True)
    def _confirm_apply(self, pb: meta.Playbook, argv: list[str], go) -> None:
        hosts = meta.playbook_hosts(self.repo, pb, self.options.limit)
        self.call_from_thread(self._show_apply_confirm, pb, argv, hosts, go)

    def _show_apply_confirm(self, pb, argv: list[str], hosts: list[str], go) -> None:
        by_name = {h.name: h for h in self.inventory.hosts}
        body = Text()
        body.append("This changes real infrastructure.\n\n")
        body.append(" ".join(shlex.quote(a) for a in argv), style="bold green")
        body.append("\n\nwould touch ", style="bold")
        body.append(f"{len(hosts)} host{'' if len(hosts) == 1 else 's'}\n", style="bold")
        if hosts:
            for name in hosts:
                host = by_name.get(name)
                address = f"  {host.address}" if host and host.address else ""
                body.append(f"  {name}{address}\n", style="yellow")
        else:
            body.append("  (could not resolve — check the playbook)\n", style="red")
        if self.options.tags:
            body.append(f"\nonly tags: {','.join(self.options.tags)}", style="cyan")
        if self.options.limit:
            body.append(f"\nlimited to: {self.options.limit}", style="cyan")
        dirty = len(self.changed)
        if dirty:
            body.append(f"\n\n{dirty} uncommitted change(s) in the repo — ctrl+g to see them",
                        style="yellow")
        self.push_screen(Confirm(f"Apply {pb.name}?", body, "Apply"), go)

    def on_playbook_table_row_selected(self) -> None:
        self._playbook_action("check")

    # Actions are dispatched to the focused widget, so they live on the app
    # but are bound on the tables above.
    def action_run(self) -> None:
        self._playbook_action("run")

    def action_check(self) -> None:
        self._playbook_action("check")

    def action_syntax(self) -> None:
        self._playbook_action("syntax")

    def action_open(self) -> None:
        pb = self.playbook
        if pb:
            self.push_screen(Viewer(str(pb.path.name), pb.path.read_text(), "yaml"))

    def action_clear(self) -> None:
        self.options.clear()
        self._render_options()
        self._render_playbook_detail()

    def action_diff(self) -> None:
        self.options.diff = not self.options.diff
        self._render_options()
        self._render_playbook_detail()

    def action_verbosity(self) -> None:
        self.options.verbosity = (self.options.verbosity + 1) % 5
        self._render_options()
        self._render_playbook_detail()

    def action_extra(self) -> None:
        def done(value: str | None) -> None:
            if value is not None:
                self.options.extra = value
                self._render_options()
                self._render_playbook_detail()

        self.push_screen(
            AskText("Extra ansible-playbook arguments", self.options.extra, "-e key=value --step"),
            done,
        )

    def action_limit(self) -> None:
        choices = [("", "all — every host the play targets")]
        choices += [(g, f"{g}  (group: {', '.join(m)})") for g, m in self.inventory.groups.items()]
        choices += [(h.name, f"{h.name}  (host: {h.address})") for h in self.inventory.hosts]

        def done(value: str | None) -> None:
            if value is not None:
                self.options.limit = value
                self._render_options()
                self._render_playbook_detail()

        self.push_screen(PickOne("Limit the run to", choices), done)

    def action_tags(self) -> None:
        pb = self.playbook
        if pb is None:
            return
        if pb.tags is None:
            self.notify("reading tags from ansible…")
            self._load_tags(pb)
            return
        self._show_tags(pb)

    @work(thread=True)
    def _load_tags(self, pb: meta.Playbook) -> None:
        tags = meta.playbook_tags(self.repo, pb)
        pb.tags = tags
        self.call_from_thread(self._show_tags, pb)

    def _show_tags(self, pb: meta.Playbook) -> None:
        def done(value: list[str] | None) -> None:
            if value is not None:
                self.options.tags = sorted(value)
                self._render_options()
                self._render_playbook_detail()

        self.push_screen(PickMany(f"Tags in {pb.name}", pb.tags or [], self.options.tags), done)

    # --- inventory actions -------------------------------------------------

    def action_ping(self) -> None:
        host = self.host
        if host:
            self._launch(["ansible", host.name, "-m", "ping"], f"ping {host.name}")

    def action_facts(self) -> None:
        host = self.host
        if host:
            self._launch(["ansible", host.name, "-m", "setup"], f"facts {host.name}")

    def action_inspect(self) -> None:
        host = self.host
        if not host:
            return
        import json

        values = host.vars if self.reveal_secrets else meta.redact(host.vars)
        suffix = "revealed" if self.reveal_secrets else "secrets masked"
        self.push_screen(
            Viewer(
                f"{host.name} — resolved vars ({suffix})",
                json.dumps(values, indent=2, default=str),
                "json",
            )
        )

    def action_reveal(self) -> None:
        self.reveal_secrets = not self.reveal_secrets
        self._render_host_detail()
        if self.reveal_secrets:
            self.notify("secrets are on screen — R hides them again", severity="warning")

    def action_ssh(self) -> None:
        host = self.host
        if not host:
            return
        user = host.vars.get("ansible_user", "root")
        target = host.address or host.name
        self._foreground(["ssh", f"{user}@{target}"])

    # --- role actions -------------------------------------------------------

    def action_defaults(self) -> None:
        role = self.role
        if not role:
            return
        path = role.path / "defaults" / "main.yml"
        if not path.exists():
            self.notify(f"{role.name} has no defaults", severity="warning")
            return
        self.push_screen(Viewer(f"{role.name}/defaults/main.yml", path.read_text(), "yaml"))

    def action_tasks(self) -> None:
        role = self.role
        if not role:
            return
        files = sorted(role.path.glob("tasks/*.yml"))
        if not files:
            return
        if len(files) == 1:
            self._view_file(files[0], role.name)
            return

        def done(value: str | None) -> None:
            if value:
                self._view_file(Path(value), role.name)

        self.push_screen(
            PickOne(f"{role.name} — task files", [(str(f), f.name) for f in files]), done
        )

    def _view_file(self, path: Path, prefix: str) -> None:
        self.push_screen(Viewer(f"{prefix}/tasks/{path.name}", path.read_text(), "yaml"))

    # --- vault actions --------------------------------------------------------

    def action_view(self) -> None:
        vault = self.vault
        if not vault:
            return
        code, out = meta.capture(
            ["ansible-vault", "view", str(vault.path.relative_to(self.repo.root))], self.repo.root
        )
        if code != 0:
            self.notify(f"could not decrypt: {out.strip()[:120]}", severity="error", timeout=10)
            return
        self.push_screen(Viewer(f"{vault.group} — decrypted", out, "yaml"))

    def action_edit(self) -> None:
        vault = self.vault
        if vault:
            self._foreground(
                ["ansible-vault", "edit", str(vault.path.relative_to(self.repo.root))]
            )

    def action_new(self) -> None:
        def done(group: str | None) -> None:
            if not group:
                return
            path = self.repo.group_vars_dir / group / "vault.yml"
            if path.exists():
                self.notify(f"{group} already has a vault", severity="warning")
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.repo.root / ".pb-new-vault.yml"
            tmp.write_text(f"---\n# Secrets for the {group} group.\n")
            code, out = meta.capture(
                ["ansible-vault", "encrypt", str(tmp.name), "--output", str(path)], self.repo.root
            )
            tmp.unlink(missing_ok=True)
            if code == 0:
                self.notify(f"created {path.relative_to(self.repo.root)}")
                self.reload()
            else:
                self.notify(out.strip()[:150], severity="error", timeout=10)

        self.push_screen(AskText("New vault for group", placeholder="service_name"), done)

    def action_rekey(self) -> None:
        def go(ok: bool | None) -> None:
            if ok:
                paths = [str(v.path.relative_to(self.repo.root)) for v in self.vaults]
                self._foreground(["ansible-vault", "rekey", *paths])

        self.push_screen(
            Confirm(
                "Rekey every vault?",
                Text(
                    "You will be prompted for the new password in a normal terminal.\n"
                    "Update .vault_pass afterwards or nothing will run.",
                ),
                "Rekey",
            ),
            go,
        )

    # --- status ------------------------------------------------------------

    def action_refresh_status(self) -> None:
        self.notify("probing hosts over ssh…")
        self._probe_hosts()

    @work(thread=True, exclusive=True)
    def _probe_hosts(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        hosts = list(self.inventory.hosts)
        if not hosts:
            return
        # One SSH round trip each, in parallel: a slow host must not hold up
        # the rest of the fleet.
        with ThreadPoolExecutor(max_workers=min(8, len(hosts))) as pool:
            results = list(pool.map(hoststatus.probe, hosts))
        self.call_from_thread(self._apply_status, results)

    def _apply_status(self, results: list[hoststatus.HostStatus]) -> None:
        self.host_status = {r.host: r for r in results}
        self._render_status_table()
        self._render_status_detail()
        down = [r.host for r in results if not r.reachable and not r.local]
        sick = [r.host for r in results if r.reachable and not r.healthy]
        if down:
            self.notify(f"unreachable: {', '.join(down)}", severity="error", timeout=10)
        elif sick:
            self.notify(f"needs attention: {', '.join(sick)}", severity="warning", timeout=8)
        else:
            self.notify("all hosts healthy")

    # --- history -------------------------------------------------------------

    def action_show_log(self) -> None:
        run = self.run_record
        if run:
            self.push_screen(Viewer(f"{run.label} — {run.when}", history.log_for(self.repo, run)))

    def action_rerun(self) -> None:
        run = self.run_record
        if run is None:
            return

        def go(ok: bool | None) -> None:
            if ok:
                self._launch(list(run.argv), f"{run.label} (repeat)")

        if run.applied:
            body = Text("Run this again, exactly as recorded?\n\n")
            body.append(" ".join(shlex.quote(a) for a in run.argv), style="bold green")
            body.append("\n\nIt applied changes the first time.", style="yellow")
            self.push_screen(Confirm("Run again?", body, "Run"), go)
        else:
            go(True)

    # --- git -----------------------------------------------------------------

    def action_changes(self) -> None:
        if not self.changed:
            self.notify("working tree is clean")
            return
        self.push_screen(Viewer("uncommitted changes", meta.git_diff(self.repo), "diff"))

    # --- updating pb --------------------------------------------------------

    def action_check_update(self) -> None:
        """Ask GitHub now, ignoring the once-a-day interval and any skip."""
        self.notify("checking for a newer pb…")
        self._check_for_update(manual=True)

    # Its own worker group: `reload()` is exclusive, and a check that cancelled
    # the startup load would leave the app looking at an empty repo.
    @work(thread=True, group="update", exclusive=True)
    def _check_for_update(self, manual: bool = False) -> None:
        result = update.check(__version__, force=manual)
        self.call_from_thread(self._update_checked, result, manual)

    def _update_checked(self, result: update.Result, manual: bool) -> None:
        self.update_release = result.release
        if result.release is None:
            if not manual:
                return
            if result.error:
                self.notify(result.error, severity="warning")
            else:
                self.notify(f"pb {__version__} is the latest version")
            return

        release = result.release
        upgrade = update.upgrade_command(release.tag)
        self.push_screen(
            UpdatePrompt(
                f"pb {release.version} is out — you are running {__version__}",
                release.notes or f"No release notes — see {release.url}",
                command=runner.quote(upgrade.argv),
                note=upgrade.manual,
                can_install=upgrade.possible,
            ),
            lambda answer: self._update_answered(release, upgrade, answer),
        )

    def _update_answered(
        self, release: update.Release, upgrade: update.Upgrade, answer: str | None
    ) -> None:
        if answer == "skip":
            update.skip(release.version)
            self.update_release = None
            self.notify(f"skipping {release.version} — ctrl+u offers it again")
            return
        if answer != "update" or not upgrade.possible:
            return
        self.notify(f"installing pb {release.version} with {upgrade.how}…", timeout=10)
        self._install_update(release, upgrade.argv)

    @work(thread=True, group="update", exclusive=True)
    def _install_update(self, release: update.Release, argv: list[str]) -> None:
        code, out = meta.capture(argv, self.repo.root, timeout=600)
        self.call_from_thread(self._update_installed, release, argv, code, out)

    def _update_installed(
        self, release: update.Release, argv: list[str], code: int, out: str
    ) -> None:
        if code != 0:
            self.bell()
            self.push_screen(
                Viewer(
                    f"updating to pb {release.version} failed (exit {code})",
                    f"$ {runner.quote(argv)}\n\n{out}",
                )
            )
            return
        # The new pb is on disk, but this process is still the old one: a
        # running Python cannot swap out the package it imported.
        update.forget_skip()
        self.update_release = None
        self.notify(
            f"pb {release.version} installed — quit and start pb again to use it",
            timeout=20,
        )

    # --- doctor ------------------------------------------------------------

    def action_recheck(self) -> None:
        self._run_doctor()

    @on(TabbedContent.TabActivated)
    def _tab_changed(self, event: TabbedContent.TabActivated) -> None:
        pane_id = event.pane.id if event.pane else None
        self._focus_pane(pane_id)
        if pane_id == "tab-doctor" and self.query_one("#doctor", DataTable).row_count == 0:
            self._run_doctor()
        elif pane_id == "tab-status" and not self.host_status:
            self.action_refresh_status()

    @work(thread=True, exclusive=True)
    def _run_doctor(self) -> None:
        self.call_from_thread(self.query_one("#doctor", DataTable).clear)

        def add(name: str, ok: bool | None, detail: str) -> None:
            mark = {True: ("✔", "green"), False: ("✘", "red"), None: ("•", "yellow")}[ok]
            self.call_from_thread(
                self.query_one("#doctor", DataTable).add_row,
                Text(name, style="bold"),
                Text(
                    f"{mark[0]} {'ok' if ok else 'warn' if ok is None else 'fail'}",
                    style=mark[1],
                ),
                Text(detail, style="dim"),
            )

        if self.update_release is None:
            add("pb", True, f"{__version__}, installed with {update.install_label()}")
        else:
            add(
                "pb",
                None,
                f"{__version__} — {self.update_release.version} is available (ctrl+u)",
            )

        code, out = meta.capture(["ansible", "--version"], self.repo.root, timeout=30)
        add("ansible", code == 0, out.splitlines()[0] if out else "not found")

        inv = self.repo.inventory
        origin = meta.INVENTORY_ORIGINS.get(
            self.repo.inventory_origin, self.repo.inventory_origin
        )
        add(
            "inventory path",
            inv.exists(),
            f"{self.repo.rel(inv)} ({origin})"
            + ("" if inv.exists() else " — does not exist"),
        )

        group_vars = self.repo.group_vars_dir
        add(
            "group_vars",
            group_vars.is_dir() or None,
            self.repo.rel(group_vars)
            + ("" if group_vars.is_dir() else " — none beside the inventory"),
        )

        pw = self.repo.vault_pass_file
        if pw.exists():
            mode = oct(pw.stat().st_mode & 0o777)
            ok = mode == "0o600"
            add("vault password", ok, f"{pw.name} {mode}" + ("" if ok else " — should be 0o600"))
        else:
            add("vault password", False, f"{pw} is missing — nothing will run")

        collections = self.repo.root / "collections" / "ansible_collections"
        installed = (
            sorted(f"{ns.name}.{c.name}" for ns in collections.glob("*") if ns.is_dir()
                   for c in ns.glob("*") if c.is_dir())
            if collections.is_dir() else []
        )
        add("collections", bool(installed), ", ".join(installed) or "run: make deps")

        for vault in self.vaults:
            rel = str(vault.path.relative_to(self.repo.root))
            if not vault.encrypted:
                add(f"vault {vault.group}", False, f"{rel} is NOT encrypted")
                continue
            code, out = meta.capture(["ansible-vault", "view", rel], self.repo.root, timeout=30)
            add(
                f"vault {vault.group}",
                code == 0,
                "decrypts cleanly" if code == 0 else out.strip()[:90],
            )

        if self.inventory.error:
            add("inventory", False, self.inventory.error[:90])
        elif self.inventory.warning:
            add("inventory", None, self.inventory.warning[:90])
        else:
            add(
                "inventory",
                bool(self.inventory.hosts),
                f"{len(self.inventory.hosts)} hosts in {len(self.inventory.groups)} groups",
            )

        for pb in self.playbooks:
            rel = self.repo.rel(pb.path)
            code, out = meta.capture(
                ["ansible-playbook", rel, "--syntax-check", *self.repo.inventory_args],
                self.repo.root,
            )
            add(f"syntax {pb.name}", code == 0, "clean" if code == 0 else out.strip()[-140:])

        code, _ = meta.capture(["ansible-lint", "--version"], self.repo.root, timeout=30)
        add(
            "ansible-lint",
            code == 0 or None,
            "installed" if code == 0 else "not installed (optional)",
        )

    # --- misc ---------------------------------------------------------------

    def action_quit(self) -> None:
        """Refuse to exit while ansible is still changing something."""
        live = next((s for s in self.screen_stack if isinstance(s, RunScreen) and s.running), None)
        if live is not None:
            self.notify(
                "a run is still going — ctrl+c cancels it, then q quits",
                severity="warning",
            )
            return
        self.exit()

    def action_help(self) -> None:
        self.push_screen(Viewer("pb — keys", HELP))

    def action_reload(self) -> None:
        self.notify("reloading…")
        self.reload()


HELP = """\
GLOBAL
  1..7          jump to a tab            ctrl+r   reload from disk
  ctrl+g        uncommitted changes      ?        this help
  ctrl+p        command palette          q        quit
  ctrl+u        check for a newer pb

  A yellow ● next to a playbook or role means its files differ from HEAD.

PLAYBOOKS
  r             apply (asks first)       c        dry run (--check --diff)
  s             syntax check             o        show the playbook source
  enter         dry run
  t  tags       l  limit                 d  --diff toggle
  v  verbosity  e  extra args            x  clear all options
  The pane on the right shows the exact command your options produce.
  Applying resolves the real host list first and shows it before you commit.

INVENTORY
  p  ping       f  gather facts          i  resolved vars
  s  ssh into the host (leaves the TUI, returns on exit)
  R  reveal secrets. ansible-inventory decrypts the vaults, so anything
     that looks like a credential is masked until you ask for it.

STATUS
  r  probe every host over ssh (read-only: uptime, disk, failed units,
     containers, certificate expiry)     s  ssh into the selected host

ROLES
  d  role defaults                       t  task files

VAULT
  v  view decrypted    e  edit in $EDITOR
  n  new group vault   k  rekey every vault

HISTORY
  Every run pb makes is recorded under .pb/runs — command, tags, exit code,
  recap, the commit it ran against, and the full output.
  o  open the saved output                a  run the same command again

DOCTOR
  r  re-run the checks

UPDATES
  pb asks github.com once a day whether there is a newer release, and shows
  you the changelog and the exact install command before anything happens.
  Skip a version and it is never offered again; esc asks again tomorrow.
  Start pb with --no-update-check, or set PB_NO_UPDATE_CHECK=1, to turn the
  check off — ctrl+u still checks when you ask for it.

WHILE A RUN IS ON SCREEN
  ctrl+c  cancel      w  toggle wrap     s  save the log
  g / G   top/bottom  esc                close
"""


def _notes(probe: hoststatus.HostStatus) -> Text:
    """The one-line "what is wrong here" column."""
    notes = Text()
    for unit in probe.failed_units:
        notes.append(f"{unit} failed ", style="bold red")
    if probe.disk_pct >= 90:
        notes.append(f"disk {probe.disk_pct}% ", style="bold red")
    if probe.get("reboot") == "yes":
        notes.append("reboot pending ", style="yellow")
    updates = probe.get("updates", "0")
    if updates.isdigit() and int(updates) > 0:
        notes.append(f"{updates} updates ", style="cyan")
    return notes if notes.plain else Text("—", style="dim")


def _short_uptime(text: str) -> str:
    """`14 weeks, 4 days, 19 hours, 54 minutes` -> `14w 4d`."""
    units = {"week": "w", "day": "d", "hour": "h", "minute": "m", "second": "s"}
    parts: list[str] = []
    for chunk in text.split(","):
        words = chunk.split()
        if len(words) == 2 and words[0].isdigit():
            suffix = units.get(words[1].rstrip("s"))
            if suffix:
                parts.append(words[0] + suffix)
    return " ".join(parts[:2]) or text


def _short(text: str, width: int = 40) -> str:
    """First sentence of a header comment, for the table column."""
    first = text.split(". ")[0].strip()
    return first if len(first) <= width else first[: width - 1] + "…"


def _wrap(text: str, width: int = 44) -> str:
    import textwrap

    return "\n".join(textwrap.wrap(text, width, subsequent_indent="    ")) or text


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="pb",
        description="A terminal console for an Ansible repository.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="a directory inside the Ansible repo (default: the working directory)",
    )
    parser.add_argument(
        "-i",
        "--inventory",
        metavar="PATH",
        help="the inventory file or directory to read (default: whatever "
        "ansible.cfg says, else the one pb can find in the repo)",
    )
    parser.add_argument(
        "--no-update-check",
        action="store_true",
        help="do not ask GitHub for a newer pb at startup (PB_NO_UPDATE_CHECK=1 "
        "does the same); ctrl+u still checks on request",
    )
    parser.add_argument("--version", action="version", version=f"pb {__version__}")
    args = parser.parse_args()

    start = Path(args.path) if args.path else Path.cwd()
    if not start.is_dir():
        print(f"pb: {start} is not a directory", file=sys.stderr)
        return 2

    # pb reads a repo, so it needs to know where the repo starts. ansible.cfg
    # marks it; without one there is nothing to show.
    root = meta.find_root(start)
    if not (root / "ansible.cfg").is_file():
        print(
            f"pb: no ansible.cfg in {start.resolve()} or any parent directory.\n"
            "pb runs inside an Ansible repository — cd into one, or give it a path.",
            file=sys.stderr,
        )
        return 2

    PbApp(root, args.inventory, check_updates=not args.no_update_check).run()
    return 0
