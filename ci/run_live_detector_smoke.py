#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


LIVE_SITES: list[dict[str, str]] = [
    {
        "group": "detection",
        "name": "rebrowser-bot-detector",
        "url": "https://bot-detector.rebrowser.net/",
    },
    {"group": "detection", "name": "incolumitas", "url": "https://bot.incolumitas.com/"},
    {"group": "detection", "name": "sannysoft", "url": "https://bot.sannysoft.com/"},
    {
        "group": "detection",
        "name": "browserscan-bot",
        "url": "https://www.browserscan.net/bot-detection",
    },
    {
        "group": "detection",
        "name": "fingerprintjs-demo",
        "url": "https://demo.fingerprint.com/web-scraping",
    },
    {"group": "detection", "name": "pixelscan", "url": "https://pixelscan.net/fingerprint-check"},
    {"group": "detection", "name": "creepjs", "url": "https://abrahamjuliot.github.io/creepjs/"},
    {"group": "detection", "name": "fingerprint-scan", "url": "https://fingerprint-scan.com/"},
    {
        "group": "detection",
        "name": "deviceinfo-bot",
        "url": "https://deviceandbrowserinfo.com/are_you_a_bot",
    },
    {"group": "fingerprint", "name": "browserleaks-canvas", "url": "https://browserleaks.com/canvas"},
    {"group": "fingerprint", "name": "browserleaks-webgl", "url": "https://browserleaks.com/webgl"},
    {"group": "fingerprint", "name": "browserleaks-fonts", "url": "https://browserleaks.com/fonts"},
    {"group": "fingerprint", "name": "browserleaks-js", "url": "https://browserleaks.com/javascript"},
    {
        "group": "fingerprint",
        "name": "fingerprintjs-oss",
        "url": "https://fingerprintjs.github.io/fingerprintjs/",
    },
    {"group": "fingerprint", "name": "audio-fp", "url": "https://audiofingerprint.openwpm.com/"},
    {"group": "fingerprint", "name": "deviceinfo", "url": "https://deviceandbrowserinfo.com/info_device"},
    {"group": "headers-tls", "name": "httpbin-headers", "url": "https://httpbin.org/headers"},
    {"group": "headers-tls", "name": "httpbin-ip", "url": "https://httpbin.org/ip"},
    {"group": "headers-tls", "name": "tls-browserleaks", "url": "https://tls.browserleaks.com/"},
    {
        "group": "recaptcha",
        "name": "google-v3-demo",
        "url": "https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php",
    },
    {"group": "recaptcha", "name": "2captcha-v3", "url": "https://2captcha.com/demo/recaptcha-v3"},
    {
        "group": "recaptcha",
        "name": "turnstile",
        "url": "https://peet.ws/turnstile-test/non-interactive.html",
    },
]


async def main() -> int:
    sys.path.insert(0, "/git/agent-zero")
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore
    from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright
    from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch

    apply_runtime_patch()
    patch_playwright()
    artifacts = Path("artifacts")
    screenshots = artifacts / "screenshots" / "live-detectors"
    screenshots.mkdir(parents=True, exist_ok=True)

    sites = _selected_sites()
    result: dict[str, Any] = {
        "ok": True,
        "fatal": False,
        "site_count": len(sites),
        "sites": [],
        "note": (
            "Live detector sites are non-gating because third-party pages are flaky "
            "and may change."
        ),
    }
    core = _BrowserRuntimeCore("cloakbrowser-live-detector-ci")
    try:
        for site in sites:
            result["sites"].append(await _probe_site(core, site, screenshots))
    except Exception as exc:
        result["fatal"] = True
        result["fatal_error"] = repr(exc)
    finally:
        await core.close(delete_profile=True)
        artifacts.mkdir(exist_ok=True)
        (artifacts / "live-detector-results.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


async def _probe_site(
    core: Any,
    site: dict[str, str],
    screenshots: Path,
) -> dict[str, Any]:
    record: dict[str, Any] = dict(site)
    try:
        opened = await asyncio.wait_for(core.open(site["url"]), timeout=_open_timeout())
        browser_page = core.pages[opened["id"]]
        page = browser_page.page
        page.set_default_timeout(_action_timeout() * 1000)
        page.set_default_navigation_timeout(_action_timeout() * 1000)
        await page.wait_for_timeout(_settle_seconds() * 1000)
        record["final_url"] = page.url
        record["title"] = await page.title()
        record["signals"] = await _page_signals(page)
        html = await page.content()
        record["text_sample"] = _text_sample(html)
        screenshot = screenshots / f"{site['group']}-{site['name']}.png"
        await page.screenshot(path=str(screenshot), full_page=True)
        record["screenshot"] = str(screenshot)
        record["ok"] = True
    except Exception as exc:
        record["ok"] = False
        record["error"] = repr(exc)
    return record


async def _page_signals(page: Any) -> dict[str, Any]:
    return await page.evaluate(
        """() => ({
          webdriver: navigator.webdriver,
          userAgent: navigator.userAgent,
          platform: navigator.platform,
          languages: navigator.languages,
          plugins: navigator.plugins.length,
          hardwareConcurrency: navigator.hardwareConcurrency,
          deviceMemory: navigator.deviceMemory || null,
          innerWidth: window.innerWidth,
          innerHeight: window.innerHeight,
          screenWidth: screen.width,
          screenHeight: screen.height,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          hasChrome: Boolean(window.chrome),
          visibilityState: document.visibilityState
        })"""
    )


def _selected_sites() -> list[dict[str, str]]:
    selected = list(LIVE_SITES)
    groups = _csv_env("CLOAKBROWSER_LIVE_GROUPS")
    if groups:
        selected = [site for site in selected if site["group"] in groups]
    names = _csv_env("CLOAKBROWSER_LIVE_SITES")
    if names:
        selected = [site for site in selected if site["name"] in names]
    limit = int(os.environ.get("CLOAKBROWSER_LIVE_SITE_LIMIT") or "0")
    if limit > 0:
        selected = selected[:limit]
    return selected


def _csv_env(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _open_timeout() -> int:
    return int(os.environ.get("CLOAKBROWSER_LIVE_OPEN_TIMEOUT") or "45")


def _action_timeout() -> int:
    return int(os.environ.get("CLOAKBROWSER_LIVE_ACTION_TIMEOUT") or "15")


def _settle_seconds() -> int:
    return int(os.environ.get("CLOAKBROWSER_LIVE_SETTLE_SECONDS") or "5")


def _text_sample(html: str) -> str:
    text = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", html, flags=re.I)
    text = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:4000]


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
