from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from plugins._browser.tools.browser import Browser as UpstreamBrowser


class Browser(UpstreamBrowser):
    async def execute(self, *args: Any, **kwargs: Any):
        from plugin_imports import plugin_import

        patch_playwright = plugin_import("helpers.playwright_shim").patch_playwright
        apply_runtime_patch = plugin_import("helpers.runtime_patch").apply_runtime_patch

        apply_runtime_patch()
        patch_playwright()
        return await super().execute(*args, **kwargs)
