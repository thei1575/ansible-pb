"""`pb plugin …` - installing and developing plugins from the command line.

Everything here is deliberately outside the TUI: installing a plugin fetches
and then runs third-party code in pb's process, so it should be something you
did on purpose at a shell prompt, with the confirmation in front of you.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import loader, manage, scaffold, source
from .api import API_VERSION
from .manifest import ManifestError
from .store import Record, Store, StoreError

# Anything the operations below can raise that is the user's problem rather
# than a bug, and so deserves a message instead of a traceback.
EXPECTED = (StoreError, ManifestError, source.SourceError)

TRUST_NOTICE = """\
A pb plugin is Python that runs inside pb, with your permissions: it can read
your repo and your vault password file, add or replace what the keys do, and
change the ansible commands pb builds. Install plugins you would give a shell
account to."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pb plugin",
        description="Install, develop and manage pb plugins.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    listed = sub.add_parser("list", aliases=["ls"], help="what is installed")
    listed.add_argument("--paths", action="store_true", help="show where each one lives")

    install = sub.add_parser(
        "install",
        aliases=["add"],
        help="install from GitHub (owner/repo), a git URL, or a local checkout",
    )
    install.add_argument("source", help="owner/repo, owner/repo@tag, a git URL, or a path")
    install.add_argument("--ref", default="", help="branch, tag or commit to pin to")
    install.add_argument("--name", default="", help="require the plugin to be called this")
    install.add_argument("--force", action="store_true", help="replace an existing install")
    install.add_argument(
        "-y", "--yes", action="store_true", help="do not ask for confirmation"
    )

    update = sub.add_parser("update", aliases=["upgrade"], help="fetch newer commits")
    update.add_argument("name", nargs="*", help="plugins to update (default: all of them)")

    remove = sub.add_parser("remove", aliases=["uninstall", "rm"], help="uninstall a plugin")
    remove.add_argument("name")

    enable = sub.add_parser("enable", help="load a plugin at start-up again")
    enable.add_argument("name")

    disable = sub.add_parser(
        "disable", help="keep a plugin installed but stop loading it"
    )
    disable.add_argument("name")

    link = sub.add_parser(
        "link", help="develop against a checkout of your own, read in place"
    )
    link.add_argument("path", nargs="?", default=".", help="the plugin directory (default: .)")
    link.add_argument("--name", default="", help="require the plugin to be called this")

    created = sub.add_parser("new", help="write a working plugin to start from")
    created.add_argument("name", help="the plugin name, e.g. pb-terraform")
    created.add_argument(
        "--dir", default=".", help="where to create it (default: the working directory)"
    )
    created.add_argument("--owner", default="your-name", help="for the README's install line")

    info = sub.add_parser("info", help="everything pb knows about one plugin")
    info.add_argument("name")

    sub.add_parser("doctor", help="load every plugin and report what went wrong")
    sub.add_parser("path", help="print the plugin directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not args.command:
        parser.print_help()
        return 0

    store = Store()
    handlers = {
        "list": _list,
        "ls": _list,
        "install": _install,
        "add": _install,
        "update": _update,
        "upgrade": _update,
        "remove": _remove,
        "uninstall": _remove,
        "rm": _remove,
        "enable": _enable,
        "disable": _disable,
        "link": _link,
        "new": _new,
        "info": _info,
        "doctor": _doctor,
        "path": _path,
    }
    try:
        return handlers[args.command](store, args)
    except EXPECTED as exc:
        print(f"pb plugin: {exc}", file=sys.stderr)
        return 1


# --- commands -----------------------------------------------------------


def _list(store: Store, args: argparse.Namespace) -> int:
    records = store.records()
    if not records:
        print("No plugins installed.")
        print("\n  pb plugin install owner/repo    install one from GitHub")
        print("  pb plugin new pb-mine           start writing your own")
        return 0

    rows = [
        (
            record.name,
            record.version or "-",
            _state(record),
            str(store.root_for(record)) if args.paths else record.origin or "-",
        )
        for record in records
    ]
    header = ("NAME", "VERSION", "STATE", "PATH" if args.paths else "SOURCE")
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(3)]
    for row in (header, *rows):
        print(f"{row[0]:<{widths[0]}}  {row[1]:<{widths[1]}}  {row[2]:<{widths[2]}}  {row[3]}")
    return 0


def _state(record: Record) -> str:
    if not record.enabled:
        return "disabled"
    if record.linked:
        return "linked"
    return f"@{record.short_commit}" if record.commit else "installed"


def _install(store: Store, args: argparse.Namespace) -> int:
    resolved = source.resolve(args.source, args.ref)
    print(f"Install a pb plugin from {resolved.url}")
    if resolved.ref:
        print(f"                     ref {resolved.ref}")
    print(f"                    into {store.dir_for(args.name or resolved.name_hint)}")
    print()
    print(TRUST_NOTICE)
    print()
    if not _confirm(args.yes, "Fetch and install it?"):
        print("Nothing was installed.")
        return 1

    done = manage.install(
        store, args.source, ref=args.ref, name=args.name, force=args.force
    )
    print(
        f"Installed {done.record.name} {done.record.version or ''}".rstrip()
        + f" at {done.record.short_commit}"
    )
    if done.manifest.summary:
        print(f"  {done.manifest.summary}")
    print("  Start pb to load it. `pb plugin doctor` checks it imports first.")
    return 0


def _update(store: Store, args: argparse.Namespace) -> int:
    names = args.name or [r.name for r in store.records() if not r.linked]
    if not names:
        print("Nothing to update.")
        return 0

    failed: list[str] = []
    for name in names:
        try:
            done = manage.update(store, name)
        except EXPECTED as exc:
            print(f"{name}: {exc}", file=sys.stderr)
            failed.append(name)
            continue
        if done.changed:
            print(f"{name}: {done.previous_commit[:7]} → {done.record.short_commit}")
        else:
            print(f"{name}: already at {done.record.short_commit}")
    if failed:
        return 1
    print("Restart pb to load the new code.")
    return 0


def _remove(store: Store, args: argparse.Namespace) -> int:
    record = manage.remove(store, args.name)
    where = "unlinked" if record.linked else "removed"
    print(f"{record.name} {where}.")
    return 0


def _enable(store: Store, args: argparse.Namespace) -> int:
    manage.set_enabled(store, args.name, True)
    print(f"{args.name} will load next time pb starts.")
    return 0


def _disable(store: Store, args: argparse.Namespace) -> int:
    manage.set_enabled(store, args.name, False)
    print(f"{args.name} is installed but will not load.")
    return 0


def _link(store: Store, args: argparse.Namespace) -> int:
    done = manage.link(store, args.path, name=args.name)
    print(f"Linked {done.record.name} → {done.record.path}")
    print("pb reads that directory in place, so an edit needs only a restart.")
    return 0


def _new(store: Store, args: argparse.Namespace) -> int:
    made = scaffold.new(args.name, Path(args.dir), owner=args.owner)
    print(f"Created {made.root}")
    for path in made.files:
        print(f"  {path.relative_to(made.root)}")
    if made.git:
        print("  (initialised as a git repository)")
    print()
    print("Try it:")
    print(f"  pb plugin link {made.root}")
    print("  pb plugin doctor")
    print("  pb ~/my-ansible-repo")
    return 0


def _info(store: Store, args: argparse.Namespace) -> int:
    fields = manage.describe(store, args.name)
    width = max(len(k) for k in fields)
    for key, value in fields.items():
        print(f"{key:<{width}}  {value}")
    return 0


def _doctor(store: Store, args: argparse.Namespace) -> int:
    print(f"plugin API      {API_VERSION}")
    print(f"config          {store.root}")
    print(f"plugins         {store.plugins_dir}")
    print(f"git             {'found' if source.have_git() else 'NOT on PATH'}")
    records = store.records()
    if not records:
        print("\nNo plugins installed.")
        return 0

    loaded = loader.load_all(store)
    print()
    for record in records:
        plugin = loaded.by_name(record.name)
        failure = next((f for f in loaded.failures if f.name == record.name), None)
        if not record.enabled:
            mark, note = "-", "disabled"
        elif failure is not None:
            mark, note = "✘", f"{failure.stage}: {failure.message}"
        elif plugin is not None:
            hooks = ", ".join(_hooks(plugin)) or "no hooks"
            note = f"loaded from {plugin.root} ({hooks})"
            mark = "✔"
        else:
            mark, note = "✘", "did not load, and said nothing about why"
        print(f"{mark} {record.name:<24} {note}")
        if failure is not None and failure.detail:
            for line in failure.detail.strip().splitlines():
                print(f"    {line}")
    return 1 if loaded.failures else 0


def _hooks(plugin: object) -> list[str]:
    """Which hooks this plugin actually overrides - the useful half of `info`."""
    from .api import Plugin

    return [
        name
        for name in (
            "tabs", "keys", "actions", "commands", "doctor",
            "reloaded", "before_run", "after_run", "detail", "status_bar", "activate",
        )
        if getattr(type(plugin), name, None) is not getattr(Plugin, name, None)
    ]


def _path(store: Store, args: argparse.Namespace) -> int:
    print(store.plugins_dir)
    return 0


def _confirm(assume_yes: bool, question: str) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(
            f"{question} - refusing to install without a terminal to ask in. "
            "Pass --yes if you meant it.",
            file=sys.stderr,
        )
        return False
    try:
        answer = input(f"{question} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")
