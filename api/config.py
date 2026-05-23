from __future__ import annotations

import importlib.util
from pathlib import Path

from helpers.api import ApiHandler, Request

_ROOT = Path(__file__).resolve().parents[1]


def _plugin_import(module: str):
    spec = importlib.util.spec_from_file_location(
        "_cloakbrowser_plugin_imports_api_config",
        _ROOT / "plugin_imports.py",
    )
    if not spec or not spec.loader:
        raise RuntimeError("CloakBrowser plugin_imports.py could not be loaded")
    plugin_imports = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin_imports)
    return plugin_imports.plugin_import(module)


class Config(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        config_helpers = _plugin_import("helpers.config")

        action = str(input.get("action") or "get").strip().lower()
        if action == "get":
            return {"ok": True, "config": config_helpers.get_config()}
        if action == "save":
            return {"ok": True, "config": config_helpers.save_config(input.get("config") or {})}
        return {"ok": False, "error": f"Unknown action: {action}"}
