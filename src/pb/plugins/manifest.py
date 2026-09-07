"""`pb-plugin.toml` — what a plugin declares about itself.

The manifest is the trust boundary and the version gate: pb reads it before it
imports a single line of plugin code, so a plugin written for an older API is
refused rather than half-loaded.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .api import API_VERSION

MANIFEST_NAME = "pb-plugin.toml"

# A plugin name goes into a directory name, a state file and a notification, so
# keep it to something that is safe in all three.
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class ManifestError(Exception):
    """The manifest is missing, unparseable, or says something impossible."""


@dataclass(frozen=True)
class Manifest:
    name: str
    version: str = "0"
    summary: str = ""
    api: int = API_VERSION
    # The module pb imports. Defaults to the name with dashes and dots
    # flattened, which is what `pb plugin new` scaffolds.
    module: str = ""
    homepage: str = ""
    # Directories added to sys.path before the import, relative to the plugin
    # root. The root itself is the default, which suits a flat layout and a
    # `src/`-less package alike.
    python_path: tuple[str, ...] = (".",)
    # Stylesheets loaded with pb's own, so a plugin's widgets can be styled.
    css: tuple[str, ...] = ()

    @property
    def import_name(self) -> str:
        return self.module or default_module(self.name)


def default_module(name: str) -> str:
    return re.sub(r"[-.]+", "_", name)


def _as_str_tuple(value: object, field_name: str, source: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ManifestError(f"{source}: [plugin] {field_name} must be a list of strings")
    return tuple(v for v in value if v)


def parse(text: str, source: Path = Path(MANIFEST_NAME)) -> Manifest:
    """Parse manifest text. Raises ManifestError on anything pb cannot use."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{source}: not valid TOML — {exc}") from exc

    table = data.get("plugin")
    if not isinstance(table, dict):
        raise ManifestError(f"{source}: no [plugin] table")

    name = table.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ManifestError(
            f"{source}: [plugin] name must be lowercase letters, digits, "
            f"'-', '_' or '.' (got {name!r})"
        )

    api = table.get("api", API_VERSION)
    if not isinstance(api, int) or isinstance(api, bool):
        raise ManifestError(f"{source}: [plugin] api must be an integer")
    if api != API_VERSION:
        raise ManifestError(
            f"{name}: written for plugin API {api}, this pb speaks {API_VERSION}"
        )

    module = table.get("module", "")
    if not isinstance(module, str):
        raise ManifestError(f"{source}: [plugin] module must be a string")
    if module and not module.replace(".", "_").isidentifier():
        raise ManifestError(f"{source}: [plugin] module {module!r} is not an importable name")
    # pb is imported and reloaded by name; a plugin claiming it would be
    # asking pb to drop itself out of sys.modules.
    if module == "pb" or module.startswith("pb."):
        raise ManifestError(f"{source}: [plugin] module cannot be {module!r} — that is pb itself")

    for key in ("version", "summary", "homepage"):
        if key in table and not isinstance(table[key], str):
            raise ManifestError(f"{source}: [plugin] {key} must be a string")

    python_path = _as_str_tuple(table.get("python_path", ["."]), "python_path", source)
    css = _as_str_tuple(table.get("css"), "css", source)
    for entry in (*python_path, *css):
        if Path(entry).is_absolute() or ".." in Path(entry).parts:
            raise ManifestError(
                f"{source}: {entry!r} must be a path inside the plugin, not absolute or ..-escaping"
            )

    return Manifest(
        name=name,
        version=str(table.get("version", "0")),
        summary=table.get("summary", ""),
        api=api,
        module=module,
        homepage=table.get("homepage", ""),
        python_path=python_path or (".",),
        css=css,
    )


def load(root: Path) -> Manifest:
    """Read `root/pb-plugin.toml`."""
    path = root / MANIFEST_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManifestError(f"{path} is missing — every pb plugin needs one") from exc
    except OSError as exc:
        raise ManifestError(f"{path}: {exc}") from exc
    return parse(text, path)


def css_paths(root: Path, manifest: Manifest) -> list[Path]:
    """Absolute paths to the plugin's stylesheets, skipping any that vanished."""
    paths = [(root / entry).resolve() for entry in manifest.css]
    return [p for p in paths if p.is_file()]
