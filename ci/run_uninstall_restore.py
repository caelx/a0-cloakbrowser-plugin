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
    result = subprocess.run(
        ["python", str(Path(plugin_dir) / "execute.py"), "uninstall", "--noninteractive"],
        check=False,
        capture_output=True,
        text=True,
    )
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/uninstall-results.json").write_text(
        json.dumps(
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
