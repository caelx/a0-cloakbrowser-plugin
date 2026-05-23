from __future__ import annotations

import importlib.util
from pathlib import Path

from helpers.api import ApiHandler, Request

_ROOT = Path(__file__).resolve().parents[1]


def _plugin_import(module: str):
    spec = importlib.util.spec_from_file_location(
        "_cloakbrowser_plugin_imports_api_install",
        _ROOT / "plugin_imports.py",
    )
    if not spec or not spec.loader:
        raise RuntimeError("CloakBrowser plugin_imports.py could not be loaded")
    plugin_imports = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin_imports)
    return plugin_imports.plugin_import(module)


class Install(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        action = str(input.get("action") or "setup").strip().lower()
        if action in {"setup", "repair"}:
            setup_plugin = _plugin_import("helpers.setup").setup_plugin

            return setup_plugin(
                noninteractive=bool(input.get("noninteractive", True)),
                skip_system_deps=bool(input.get("skip_system_deps", False)),
            )
        if action == "uninstall":
            uninstall = _plugin_import("helpers.uninstall").uninstall

            return uninstall(remove_extensions=bool(input.get("remove_extensions", False)))
        return {"ok": False, "error": f"Unknown action: {action}"}
