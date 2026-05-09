#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    repo = os.environ.get("CLOAKBROWSER_PLUGIN_REPO", "https://github.com/caelx/a0-cloakbrowser-plugin.git")
    plugin_name = "cloakbrowser"
    sys.path.insert(0, "/git/agent-zero")
    from plugins._plugin_installer.helpers.install import install_from_git
    from helpers import plugins

    existing = plugins.find_plugin_dir(plugin_name)
    if existing:
        print(json.dumps({"ok": True, "plugin_name": plugin_name, "path": existing, "already_installed": True}))
        return 0
    result = install_from_git(repo, plugin_name=plugin_name)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
