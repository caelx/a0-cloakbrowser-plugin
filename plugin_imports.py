from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def plugin_import(module: str):
    root = Path(__file__).resolve().parent
    ensure_agent_zero_path(root)
    removed_entries: list[tuple[int, str]] = []
    try:
        for index, entry in reversed(list(enumerate(sys.path))):
            try:
                matches_root = Path(entry or ".").resolve() == root
            except Exception:
                matches_root = False
            if entry == str(root) or matches_root:
                removed_entries.append((index, entry))
                sys.path.pop(index)
        return importlib.import_module(f"usr.plugins.cloakbrowser.{module}")
    except ModuleNotFoundError as exc:
        target = f"usr.plugins.cloakbrowser.{module}"
        if exc.name not in {"usr", "usr.plugins", "usr.plugins.cloakbrowser", target}:
            raise
    finally:
        for index, entry in sorted(removed_entries):
            sys.path.insert(min(index, len(sys.path)), entry)
    if module.startswith("helpers."):
        package = sys.modules.setdefault("cloakbrowser_local", types.ModuleType("cloakbrowser_local"))
        package.__path__ = [str(root)]
        helpers_package = sys.modules.setdefault(
            "cloakbrowser_local.helpers",
            types.ModuleType("cloakbrowser_local.helpers"),
        )
        helpers_package.__path__ = [str(root / "helpers")]
        return importlib.import_module(f"cloakbrowser_local.{module}")
    return importlib.import_module(module)


def ensure_agent_zero_path(root: Path | None = None) -> None:
    root = root or Path(__file__).resolve().parent
    for parent in root.parents:
        if (parent / "plugins" / "_browser").is_dir() and (parent / "helpers" / "tool.py").is_file():
            parent_str = str(parent)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)
            return
