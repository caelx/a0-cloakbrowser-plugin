#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

try:
    from runtime_paths import bootstrap
except ImportError:
    from ci.runtime_paths import bootstrap


ZIPERTO_URL = "https://www.ziperto.com/"


async def main() -> int:
    bootstrap()
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore
    from usr.plugins.cloakbrowser.helpers.extensions import active_extension_paths
    from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright, status
    from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch

    artifacts = Path(os.environ.get("CLOAKBROWSER_ARTIFACTS_DIR") or "artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    screenshot = artifacts / "ziperto-probe.png"
    wait_ms = int(os.environ.get("CLOAKBROWSER_ZIPERTO_WAIT_MS") or "20000")
    started = time.monotonic()
    result: dict[str, Any] = {"url": ZIPERTO_URL, "screenshot": str(screenshot), "wait_ms": wait_ms}

    apply_runtime_patch()
    patch_playwright()
    core = _BrowserRuntimeCore("cloakbrowser-ziperto-probe")
    try:
        opened = await core.open(ZIPERTO_URL)
        browser_id = opened["id"]
        page = core.pages[browser_id].page
        page.set_default_timeout(30000)
        await page.wait_for_timeout(wait_ms)
        title = await page.title()
        text = await page.locator("body").inner_text(timeout=5000)
        environment = await page.evaluate(
            """() => ({
              webdriver: navigator.webdriver,
              userAgent: navigator.userAgent,
              platform: navigator.platform,
              language: navigator.language,
              languages: navigator.languages,
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
              locale: Intl.DateTimeFormat().resolvedOptions().locale,
              innerWidth: window.innerWidth,
              innerHeight: window.innerHeight,
              screenWidth: screen.width,
              screenHeight: screen.height
            })"""
        )
        await page.screenshot(path=str(screenshot), full_page=True)
        lower_text = text.lower()
        result.update(
            {
                "final_url": page.url,
                "title": title,
                "body_excerpt": text[:1000],
                "markers": {
                    "cloudflare": "cloudflare" in lower_text,
                    "just_a_moment": "just a moment" in lower_text,
                    "security_verification": "security verification" in lower_text,
                },
                "environment": environment,
                "extensions": active_extension_paths(),
                "shim": status(),
                "passed": not looks_cloudflare_blocked(title, text),
            }
        )
    except Exception as exc:
        result.update({"passed": False, "error": str(exc)})
    finally:
        try:
            await core.close(delete_profile=False)
        finally:
            result["elapsed_seconds"] = round(time.monotonic() - started, 2)
            (artifacts / "ziperto-probe.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    if os.environ.get("CLOAKBROWSER_ZIPERTO_STRICT") == "1" and not result.get("passed"):
        return 1
    return 0


def looks_cloudflare_blocked(title: str, text: str) -> bool:
    haystack = f"{title}\n{text}".lower()
    return (
        "just a moment" in haystack
        or "security verification" in haystack
        or ("cloudflare" in haystack and "verify you are human" in haystack)
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
