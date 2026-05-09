#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


async def main() -> int:
    sys.path.insert(0, "/git/agent-zero")
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore
    from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch
    from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright

    apply_runtime_patch()
    patch_playwright()
    artifacts = Path("artifacts")
    screenshots = artifacts / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    core = _BrowserRuntimeCore("cloakbrowser-live-detector-ci")
    result: dict[str, object] = {"url": "https://bot.sannysoft.com/"}
    try:
        opened = await core.open(result["url"])
        await asyncio.sleep(5)
        browser_page = core.pages[opened["id"]]
        page = browser_page.page
        result["state"] = {"url": page.url, "title": await page.title()}
        result["text"] = (await page.content())[:20000]
        screenshot = screenshots / "live-detector-sannysoft.png"
        await page.screenshot(path=str(screenshot), full_page=True)
        result["screenshot"] = str(screenshot)
    except Exception as exc:
        result["error"] = repr(exc)
    finally:
        await core.close(delete_profile=True)
        artifacts.mkdir(exist_ok=True)
        (artifacts / "live-detector-results.json").write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
