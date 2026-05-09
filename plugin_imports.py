from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def plugin_import(module: str):
    root = Path(__file__).resolve().parent
    ensure_agent_zero_path(root)
    removed = False
    try:
        if str(root) in sys.path:
            sys.path.remove(str(root))
            removed = True
        return importlib.import_module(f"usr.plugins.cloakbrowser.{module}")
    except ModuleNotFoundError:
        pass
    finally:
        if removed:
            sys.path.insert(0, str(root))
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
