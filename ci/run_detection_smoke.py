#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
from pathlib import Path

try:
    from runtime_paths import bootstrap
except ImportError:
    from ci.runtime_paths import bootstrap


async def main() -> int:
    bootstrap()
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore
    from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch
    from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright, status

    apply_runtime_patch()
    patch_playwright()
    core = _BrowserRuntimeCore("cloakbrowser-detection-ci")
    results = {}
    try:
        opened = await core.open("data:text/html,<title>detection</title>")
        bid = opened["id"]
        results = await core.evaluate(
            bid,
            """({
              webdriver: navigator.webdriver,
              userAgent: navigator.userAgent,
              hasChrome: Boolean(window.chrome),
              plugins: navigator.plugins.length,
              innerWidth: window.innerWidth,
              innerHeight: window.innerHeight,
              screenWidth: screen.width,
              screenHeight: screen.height
            })""",
        )
        results["shim"] = status()
        await core.close(delete_profile=False)
    finally:
        Path("artifacts").mkdir(exist_ok=True)
        Path("artifacts/local-detection-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    value = results.get("result", {})
    assert value.get("webdriver") is not True
    assert "HeadlessChrome" not in value.get("userAgent", "")
    assert value.get("hasChrome") is True
    assert int(value.get("plugins") or 0) > 0
    assert value.get("innerWidth") == 1440
    assert value.get("innerHeight") == 960
    assert value.get("screenWidth") == 1440
    assert value.get("screenHeight") == 960
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
