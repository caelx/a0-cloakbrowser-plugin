#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


async def main() -> int:
    sys.path.insert(0, "/git/agent-zero")
    from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch
    from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright, status
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore

    apply_runtime_patch()
    patch_playwright()
    core = _BrowserRuntimeCore("cloakbrowser-runtime-ci")
    result = {"profile_dir": str(core.profile_dir)}
    try:
        await core.open("data:text/html,<title>runtime</title>")
        result["pages"] = len(core.pages)
        result["shim"] = status()
        await core.close(delete_profile=False)
    finally:
        Path("artifacts").mkdir(exist_ok=True)
        Path("artifacts/runtime-smoke-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
