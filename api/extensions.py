from __future__ import annotations

import importlib.util
from pathlib import Path

from helpers.api import ApiHandler, Request

_ROOT = Path(__file__).resolve().parents[1]


def _plugin_import(module: str):
    spec = importlib.util.spec_from_file_location(
        "_cloakbrowser_plugin_imports_api_extensions",
        _ROOT / "plugin_imports.py",
    )
    if not spec or not spec.loader:
        raise RuntimeError("CloakBrowser plugin_imports.py could not be loaded")
    plugin_imports = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin_imports)
    return plugin_imports.plugin_import(module)


class Extensions(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        extension_helpers = _plugin_import("helpers.extensions")
        config_helpers = _plugin_import("helpers.config")
        manifest_helpers = _plugin_import("helpers.install_manifest")

        action = str(input.get("action") or "list").strip().lower()
        cfg = config_helpers.get_config()
        if action == "list":
            return {"ok": True, "extensions": extension_helpers.list_extension_status(cfg)}
        if action == "sync":
            return {"ok": True, "active_paths": extension_helpers.sync_browser_extension_paths(cfg)}
        if action == "install_configured":
            manifest = manifest_helpers.load_manifest()
            installed = extension_helpers.install_configured_extensions(cfg, manifest)
            manifest_helpers.save_manifest(manifest)
            return {"ok": True, "installed": installed, "extensions": extension_helpers.list_extension_status(cfg)}
        if action == "uninstall":
            result = extension_helpers.uninstall_managed_extension(
                str(input.get("key") or ""),
                remove_files=bool(input.get("remove_files", False)),
            )
            return {"ok": True, **result, "extensions": extension_helpers.list_extension_status(cfg)}
        return {"ok": False, "error": f"Unknown action: {action}"}
