from __future__ import annotations

import importlib.util
from pathlib import Path

from helpers.api import ApiHandler, Request

_ROOT = Path(__file__).resolve().parents[1]


def _plugin_import(module: str):
    spec = importlib.util.spec_from_file_location(
        "_cloakbrowser_plugin_imports_api_status",
        _ROOT / "plugin_imports.py",
    )
    if not spec or not spec.loader:
        raise RuntimeError("CloakBrowser plugin_imports.py could not be loaded")
    plugin_imports = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin_imports)
    return plugin_imports.plugin_import(module)


class Status(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        collect_status = _plugin_import("helpers.diagnostics").collect_status

        return collect_status()
