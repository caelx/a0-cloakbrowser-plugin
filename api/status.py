from __future__ import annotations

import sys
from pathlib import Path

from helpers.api import ApiHandler, Request

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class Status(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        from plugin_imports import plugin_import

        collect_status = plugin_import("helpers.diagnostics").collect_status

        return collect_status()
