#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, "/git/agent-zero")
    from usr.plugins.cloakbrowser.helpers.extensions import active_extension_paths, list_extension_status, sync_browser_extension_paths
    from plugins._browser.helpers.config import get_browser_config, build_browser_launch_config

    active = sync_browser_extension_paths()
    browser_config = get_browser_config()
    launch = build_browser_launch_config(browser_config)
    result = {
        "active_paths": active,
        "extensions": list_extension_status(),
        "browser_extension_paths": browser_config.get("extension_paths", []),
        "launch_args": launch.get("args", []),
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/extension-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert all(path in browser_config.get("extension_paths", []) for path in active)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
