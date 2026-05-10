from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
for _parent in _ROOT.parents:
    if (_parent / "plugins" / "_browser").is_dir() and (_parent / "helpers" / "tool.py").is_file():
        _parent_str = str(_parent)
        if _parent_str not in sys.path:
            sys.path.insert(0, _parent_str)
        break

from plugins._browser.tools.browser import Browser as UpstreamBrowser  # noqa: E402


class Browser(UpstreamBrowser):
    async def execute(self, *args: Any, **kwargs: Any):
        try:
            from ..plugin_imports import plugin_import
        except ImportError:
            from plugin_imports import plugin_import

        patch_playwright = plugin_import("helpers.playwright_shim").patch_playwright
        apply_runtime_patch = plugin_import("helpers.runtime_patch").apply_runtime_patch

        apply_runtime_patch()
        patch_playwright()
        return await super().execute(*args, **kwargs)
