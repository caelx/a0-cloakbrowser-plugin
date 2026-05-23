from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _plugin_import(module: str):
    spec = importlib.util.spec_from_file_location(
        "_cloakbrowser_plugin_imports_hooks",
        _ROOT / "plugin_imports.py",
    )
    if not spec or not spec.loader:
        raise RuntimeError("CloakBrowser plugin_imports.py could not be loaded")
    plugin_imports = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin_imports)
    return plugin_imports.plugin_import(module)


def install():
    root = Path(__file__).resolve().parent
    if root.name != "cloakbrowser":
        # Git installs should land in Agent Zero's canonical usr/plugins root.
        pass
    (root / ".cloakbrowser" / "extensions").mkdir(parents=True, exist_ok=True)
    (root / ".cloakbrowser" / "playwright").mkdir(parents=True, exist_ok=True)
    return True


def uninstall():
    result = _plugin_import("helpers.uninstall").uninstall(remove_extensions=True)
    return bool(result.get("ok")) if isinstance(result, dict) else bool(result)


def get_plugin_config(default=None, **kwargs):
    return _plugin_import("helpers.config").normalize_config(default if isinstance(default, dict) else {})


def save_plugin_config(settings=None, **kwargs):
    return _plugin_import("helpers.config").normalize_config(settings if isinstance(settings, dict) else {})
