from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def plugin_import(module: str):
    root = Path(__file__).resolve().parent
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
