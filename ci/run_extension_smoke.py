#!/usr/bin/env python3
from __future__ import annotations

import json
import copy
import sys
from pathlib import Path


def main() -> int:
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
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/extension-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert all(path in browser_config.get("extension_paths", []) for path in active)
    assert Path(bpc_path, "manifest.json").is_file()
    assert bpc_path in enabled_browser_config.get("extension_paths", [])
    assert bpc_path not in disabled_browser_config.get("extension_paths", [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
