#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def main() -> int:
    result = subprocess.run(
        ["python", "/a0/usr/plugins/cloakbrowser/execute.py", "uninstall", "--noninteractive"],
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
