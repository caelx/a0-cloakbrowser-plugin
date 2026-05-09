from __future__ import annotations

import sys
from pathlib import Path

from helpers.api import ApiHandler, Request

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class Install(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        from plugin_imports import plugin_import

        action = str(input.get("action") or "setup").strip().lower()
        if action in {"setup", "repair"}:
            setup_plugin = plugin_import("helpers.setup").setup_plugin

            return setup_plugin(
                noninteractive=bool(input.get("noninteractive", True)),
                skip_system_deps=bool(input.get("skip_system_deps", False)),
            )
        if action == "uninstall":
            uninstall = plugin_import("helpers.uninstall").uninstall

            return uninstall(remove_extensions=bool(input.get("remove_extensions", False)))
        return {"ok": False, "error": f"Unknown action: {action}"}
