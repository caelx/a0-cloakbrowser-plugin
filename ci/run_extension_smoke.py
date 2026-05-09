#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import copy
import sys
from pathlib import Path


async def main() -> int:
    sys.path.insert(0, "/git/agent-zero")
    from usr.plugins.cloakbrowser.helpers.config import get_config
    from usr.plugins.cloakbrowser.helpers.extensions import (
        active_extension_paths,
        install_configured_extensions,
        list_extension_status,
        managed_extension_paths,
        sync_browser_extension_paths,
    )
    from plugins._browser.helpers.config import get_browser_config, build_browser_launch_config

    active = sync_browser_extension_paths()
    browser_config = get_browser_config()
    launch = build_browser_launch_config(browser_config)
    bpc_enabled_config = copy.deepcopy(get_config())
    bpc_enabled_config["extensions"]["install_bypass_paywalls_clean"] = True
    bpc_enabled_config["extensions"]["enable_bypass_paywalls_clean"] = True
    bpc_enabled_config["extensions"]["update_bypass_paywalls_clean_on_setup"] = True
    manifest: dict[str, object] = {}
    installed = install_configured_extensions(bpc_enabled_config, manifest)
    bpc_path = str(managed_extension_paths()["bypass_paywalls_clean"])
    enabled_paths = sync_browser_extension_paths(bpc_enabled_config)
    enabled_browser_config = get_browser_config()

    bpc_disabled_config = copy.deepcopy(bpc_enabled_config)
    bpc_disabled_config["extensions"]["enable_bypass_paywalls_clean"] = False
    disabled_paths = sync_browser_extension_paths(bpc_disabled_config)
    disabled_browser_config = get_browser_config()

    result = {
        "active_paths": active,
        "extensions": list_extension_status(),
        "browser_extension_paths": browser_config.get("extension_paths", []),
        "launch_args": launch.get("args", []),
        "bypass_paywalls_clean": {
            "installed": "bypass_paywalls_clean" in installed or Path(bpc_path, "manifest.json").is_file(),
            "path": bpc_path,
            "enabled_paths": enabled_paths,
            "enabled_browser_extension_paths": enabled_browser_config.get("extension_paths", []),
            "disabled_paths": disabled_paths,
            "disabled_browser_extension_paths": disabled_browser_config.get("extension_paths", []),
            "metadata": manifest.get("extensions", {}).get("bypass_paywalls_clean", {}),
        },
    }
    result["ublock_origin_lite_probe"] = await run_ubol_probe()
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/extension-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert all(path in browser_config.get("extension_paths", []) for path in active)
    assert Path(bpc_path, "manifest.json").is_file()
    assert bpc_path in enabled_browser_config.get("extension_paths", [])
    assert bpc_path not in disabled_browser_config.get("extension_paths", [])
    assert result["ublock_origin_lite_probe"]["matched"], result["ublock_origin_lite_probe"]
    return 0


async def run_ubol_probe() -> dict[str, object]:
    from usr.plugins.cloakbrowser.helpers.extensions import managed_extension_paths
    from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch
    from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore

    static_match = installed_ubol_ruleset_match(managed_extension_paths()["ublock_origin_lite"])
    apply_runtime_patch()
    patch_playwright()
    core = _BrowserRuntimeCore("cloakbrowser-ubol-ci")
    blocked: list[str] = []
    failed: list[tuple[str, str]] = []
    finished: list[str] = []
    probe_urls = (
        "https://ad.doubleclick.net/cloakbrowser-ad-probe.gif",
        "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js",
        "https://scorecardresearch.com/cloakbrowser-ad-probe.gif",
    )
    try:
        await core.open("https://example.com")
        browser_page = next(iter(core.pages.values()))
        page = browser_page.page
        page.set_default_timeout(15000)
        page.set_default_navigation_timeout(15000)

        def on_request_failed(request):
            failure = request.failure or ""
            failed.append((request.url, failure))
            if "ERR_BLOCKED_BY_CLIENT" in failure:
                blocked.append(request.url)

        page.on("requestfailed", on_request_failed)
        page.on("requestfinished", lambda request: finished.append(request.url))
        for probe_url in probe_urls:
            await page.evaluate(
                """url => new Promise(resolve => {
                    const img = document.createElement("img");
                    img.src = `${url}?cloakbrowserSmoke=${Date.now()}`;
                    img.onload = () => resolve();
                    img.onerror = () => resolve();
                    document.body.appendChild(img);
                    setTimeout(resolve, 4000);
                })""",
                probe_url,
            )
            if blocked:
                break
        await page.wait_for_timeout(1000)
        return {
            "blocked": blocked,
            "failed": failed,
            "finished": finished,
            "static_ruleset_match": static_match,
            "matched": bool(static_match.get("matched")),
        }
    finally:
        await core.close(delete_profile=True)


def installed_ubol_ruleset_match(extension_dir: Path) -> dict[str, object]:
    manifest = json.loads((extension_dir / "manifest.json").read_text(encoding="utf-8"))
    resources = manifest.get("declarative_net_request", {}).get("rule_resources", [])
    enabled = [item for item in resources if item.get("enabled")]
    for resource in enabled:
        rules_path = extension_dir / str(resource.get("path", "")).lstrip("/")
        if not rules_path.is_file():
            continue
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
        for rule in rules:
            if rule.get("action", {}).get("type") != "block":
                continue
            condition = rule.get("condition", {})
            domains = set(condition.get("requestDomains") or [])
            if {"3lift.com", "scorecardresearch.com"} & domains:
                return {
                    "matched": True,
                    "ruleset": resource.get("id"),
                    "rule_id": rule.get("id"),
                    "domains": sorted({"3lift.com", "scorecardresearch.com"} & domains),
                }
    return {"matched": False, "enabled_rulesets": [item.get("id") for item in enabled]}


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
