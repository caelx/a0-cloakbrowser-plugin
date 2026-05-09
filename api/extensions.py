from __future__ import annotations

import sys
from pathlib import Path

from helpers.api import ApiHandler, Request

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class Extensions(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        from plugin_imports import plugin_import

        extension_helpers = plugin_import("helpers.extensions")
        config_helpers = plugin_import("helpers.config")
        manifest_helpers = plugin_import("helpers.install_manifest")

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
