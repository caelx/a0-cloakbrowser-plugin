#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from runtime_paths import bootstrap
except ImportError:
    from ci.runtime_paths import bootstrap


@dataclass(frozen=True)
class LiveTarget:
    name: str
    category: str
    url: str
    wait_ms: int = 5000
    skip_reason: str = ""


LIVE_TARGETS: tuple[LiveTarget, ...] = (
    LiveTarget("rebrowser-bot-detector", "detection", "https://bot-detector.rebrowser.net/"),
    LiveTarget("incolumitas", "detection", "https://bot.incolumitas.com/"),
    LiveTarget("sannysoft", "detection", "https://bot.sannysoft.com/"),
    LiveTarget("browserscan-bot", "detection", "https://www.browserscan.net/bot-detection"),
    LiveTarget("fingerprintjs-demo", "detection", "https://demo.fingerprint.com/web-scraping"),
    LiveTarget("pixelscan", "detection", "https://pixelscan.net/fingerprint-check"),
    LiveTarget("creepjs", "detection", "https://abrahamjuliot.github.io/creepjs/"),
    LiveTarget("fingerprint-scan", "detection", "https://fingerprint-scan.com/"),
    LiveTarget("deviceinfo-bot", "detection", "https://deviceandbrowserinfo.com/are_you_a_bot"),
    LiveTarget("browserleaks-canvas", "fingerprint", "https://browserleaks.com/canvas"),
    LiveTarget("browserleaks-webgl", "fingerprint", "https://browserleaks.com/webgl"),
    LiveTarget("browserleaks-fonts", "fingerprint", "https://browserleaks.com/fonts"),
    LiveTarget("browserleaks-js", "fingerprint", "https://browserleaks.com/javascript"),
    LiveTarget(
        "fingerprintjs-oss", "fingerprint", "https://fingerprintjs.github.io/fingerprintjs/"
    ),
    LiveTarget("deviceinfo", "fingerprint", "https://deviceandbrowserinfo.com/info_device"),
    LiveTarget("httpbin-headers", "headers-tls", "https://httpbin.org/headers", wait_ms=1000),
    LiveTarget("httpbin-ip", "headers-tls", "https://httpbin.org/ip", wait_ms=1000),
    LiveTarget("tls-browserleaks", "headers-tls", "https://tls.browserleaks.com/"),
    LiveTarget(
        "google-recaptcha-v3",
        "captcha",
        "https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php",
    ),
    LiveTarget("2captcha-recaptcha-v3", "captcha", "https://2captcha.com/demo/recaptcha-v3"),
    LiveTarget("turnstile", "captcha", "https://peet.ws/turnstile-test/non-interactive.html"),
)

SKIPPED_TARGETS: tuple[LiveTarget, ...] = (
    LiveTarget(
        "audio-fp",
        "fingerprint",
        "https://audiofingerprint.openwpm.com/",
        skip_reason="Endpoint currently fails TLS verification with an expired certificate.",
    ),
)


async def main() -> int:
    bootstrap()
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore
    from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright
    from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch

    apply_runtime_patch()
    patch_playwright()
    artifacts = Path("artifacts")
    screenshots = artifacts / "screenshots" / "live-detectors"
    screenshots.mkdir(parents=True, exist_ok=True)
    targets = selected_targets(os.environ.get("CLOAKBROWSER_LIVE_DETECTOR_TARGETS", "all"))
    strict = os.environ.get("CLOAKBROWSER_LIVE_DETECTOR_STRICT", "0") == "1"
    core = _BrowserRuntimeCore("cloakbrowser-live-detector-ci")
    result: dict[str, Any] = {
        "strict": strict,
        "targets": [],
        "skipped": [asdict(target) for target in SKIPPED_TARGETS],
    }
    try:
        for target in targets:
            result["targets"].append(await probe_target(core, target, screenshots))
    finally:
        await core.close(delete_profile=True)
        artifacts.mkdir(exist_ok=True)
        (artifacts / "live-detector-results.json").write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
    if strict and live_failures(result["targets"]):
        return 1
    return 0


async def probe_target(core: Any, target: LiveTarget, screenshots: Path) -> dict[str, Any]:
    result: dict[str, Any] = {**asdict(target), "status": "ok", "checks": []}
    try:
        opened = await core.open(target.url)
        browser_page = core.pages[opened["id"]]
        page = browser_page.page
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(30000)
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
        except Exception as exc:
            result.setdefault("warnings", []).append(f"domcontentloaded: {exc!r}")
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as exc:
            result.setdefault("warnings", []).append(f"networkidle: {exc!r}")
        await page.wait_for_timeout(target.wait_ms)
        result["state"] = {"url": page.url, "title": await page.title()}
        result["environment"] = await browser_environment(page)
        result["text"] = await page_text(page)
        screenshot = screenshots / f"{target.category}-{target.name}.png"
        await page.screenshot(path=str(screenshot))
        result["screenshot"] = str(screenshot)
        if reason := unavailable_target_reason(target, result):
            result["status"] = "skipped"
            result["skip_reason"] = reason
            result["checks"] = []
            return result
        result["checks"] = target_checks(target, result)
    except Exception as exc:
        result["status"] = "error"
        result["error"] = repr(exc)
    return result


async def browser_environment(page: Any) -> dict[str, Any]:
    return await page.evaluate(
        """({
          webdriver: navigator.webdriver,
          userAgent: navigator.userAgent,
          platform: navigator.platform,
          languages: navigator.languages,
          plugins: navigator.plugins.length,
          innerWidth: window.innerWidth,
          innerHeight: window.innerHeight,
          screenWidth: screen.width,
          screenHeight: screen.height
        })"""
    )


async def page_text(page: Any) -> str:
    try:
        text = await page.locator("body").inner_text(timeout=5000)
    except Exception:
        text = await page.content()
    return text[:20000]


def target_checks(target: LiveTarget, result: dict[str, Any]) -> list[dict[str, Any]]:
    checks = [
        check("page loaded", bool(result.get("state", {}).get("url"))),
        check("page has title or body text", bool(result.get("state", {}).get("title") or result.get("text"))),
        check("screenshot was created", bool(result.get("screenshot")) and Path(str(result["screenshot"])).is_file()),
        check(
            "navigator.webdriver is not true", result["environment"].get("webdriver") is not True
        ),
        check(
            "user agent does not expose HeadlessChrome",
            "HeadlessChrome" not in str(result["environment"].get("userAgent", "")),
        ),
        check(
            "viewport is 1440x960",
            result["environment"].get("innerWidth") == 1440
            and result["environment"].get("innerHeight") == 960,
        ),
        check(
            "screen is 1440x960",
            result["environment"].get("screenWidth") == 1440
            and result["environment"].get("screenHeight") == 960,
        ),
    ]
    if target.name == "httpbin-headers":
        payload = extract_json_object(str(result.get("text", "")))
        headers = payload.get("headers", {}) if isinstance(payload, dict) else {}
        user_agent = str(headers.get("User-Agent", ""))
        checks.append(check("httpbin returned request headers", bool(headers)))
        checks.append(
            check(
                "httpbin user agent does not expose HeadlessChrome",
                "HeadlessChrome" not in user_agent,
            )
        )
    elif target.name == "httpbin-ip":
        payload = extract_json_object(str(result.get("text", "")))
        checks.append(check("httpbin returned origin IP", bool(payload.get("origin"))))
    return checks


def check(name: str, passed: bool) -> dict[str, Any]:
    return {"name": name, "status": "passed" if passed else "failed"}


def live_failures(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = []
    for result in results:
        if result.get("status") == "skipped":
            continue
        if result.get("status") != "ok":
            failures.append(result)
            continue
        if any(check.get("status") != "passed" for check in result.get("checks", [])):
            failures.append(result)
    return failures


def selected_targets(value: str) -> list[LiveTarget]:
    by_name = {target.name: target for target in LIVE_TARGETS}
    requested = [item.strip() for item in re.split(r"[,\s]+", value) if item.strip()]
    if not requested or requested == ["all"]:
        return list(LIVE_TARGETS)
    unknown = sorted(set(requested) - set(by_name))
    if unknown:
        raise SystemExit(
            f"Unknown CLOAKBROWSER_LIVE_DETECTOR_TARGETS entries: {', '.join(unknown)}"
        )
    return [by_name[name] for name in requested]


def unavailable_target_reason(target: LiveTarget, result: dict[str, Any]) -> str:
    if not target.name.startswith("httpbin-"):
        return ""
    title = str(result.get("state", {}).get("title", ""))
    text = str(result.get("text", ""))
    if re.search(r"\b(502|503|504)\b", title) or re.search(
        r"\b(502|503|504)\s+(Bad Gateway|Service Unavailable|Gateway Timeout)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return "httpbin returned a transient 5xx response"
    return ""


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
