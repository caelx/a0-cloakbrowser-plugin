#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, "/git/agent-zero")
    from helpers import plugins

    plugin_dir = plugins.find_plugin_dir("cloakbrowser")
    if not plugin_dir:
        raise SystemExit("cloakbrowser plugin directory not found")
    from plugins._browser.helpers.config import get_browser_config

    manifest_path = Path(plugin_dir) / ".cloakbrowser-install-manifest.json"
    manifest_before = json.loads(manifest_path.read_text(encoding="utf-8"))
    masquerade = Path(manifest_before.get("playwright_shim", {}).get("masquerade_path") or "")
    runtime_profile = Path("/git/agent-zero/tmp/browser/sessions/cloakbrowser-runtime-ci")
    before_config = get_browser_config()
    result = subprocess.run(
        ["python", str(Path(plugin_dir) / "execute.py"), "uninstall", "--noninteractive", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    parsed_stdout = {}
    if result.stdout.strip():
        parsed_stdout = json.loads(result.stdout)
    after_config = get_browser_config()
    managed_paths = {
        str(Path(plugin_dir) / ".cloakbrowser" / "extensions" / "ublock-origin-lite"),
        str(Path(plugin_dir) / ".cloakbrowser" / "extensions" / "i-still-dont-care-about-cookies"),
        str(Path(plugin_dir) / ".cloakbrowser" / "extensions" / "bypass-paywalls-clean"),
    }
    after_extension_paths = set(after_config.get("extension_paths", []))
    assertions = {
        "managed_extension_paths_disabled": not (managed_paths & after_extension_paths),
        "masquerade_removed": not masquerade.exists(),
        "runtime_profile_preserved": runtime_profile.exists(),
        "uninstall_ok": parsed_stdout.get("ok") is True,
        "runtime_patch_unpatched": parsed_stdout.get("runtime_patch", {}).get("patched") is False,
        "playwright_shim_unpatched": parsed_stdout.get("playwright_shim", {}).get("patched") is False,
    }
    if parsed_stdout.get("supervisor", {}).get("removed"):
        assertions["supervisor_config_removed"] = not Path(parsed_stdout["supervisor"]["removed"]).exists()
    stock_browser_launch = {
        "skipped": True,
        "reason": (
            "Skipped because uninstall removes the CloakBrowser masquerade and stock Playwright "
            "Chromium may not be installed in the Agent Zero image."
        ),
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/uninstall-results.json").write_text(
        json.dumps(
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "parsed_stdout": parsed_stdout,
                "before_extension_paths": before_config.get("extension_paths", []),
                "after_extension_paths": after_config.get("extension_paths", []),
                "masquerade_path": str(masquerade),
                "runtime_profile": str(runtime_profile),
                "stock_browser_launch": stock_browser_launch,
                "assertions": assertions,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert all(assertions.values()), assertions
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
