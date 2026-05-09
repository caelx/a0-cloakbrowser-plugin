from __future__ import annotations

import sys
from pathlib import Path

from helpers.api import ApiHandler, Request

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class Config(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        from plugin_imports import plugin_import

        config_helpers = plugin_import("helpers.config")

        action = str(input.get("action") or "get").strip().lower()
        if action == "get":
            return {"ok": True, "config": config_helpers.get_config()}
        if action == "save":
            return {"ok": True, "config": config_helpers.save_config(input.get("config") or {})}
        return {"ok": False, "error": f"Unknown action: {action}"}
