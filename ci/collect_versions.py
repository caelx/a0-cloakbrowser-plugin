#!/usr/bin/env python3
from __future__ import annotations

import importlib.metadata
import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    out = {
        "python": os.sys.version,
        "agent_zero_commit": _git_commit("/git/agent-zero"),
        "cloakbrowser": _version("cloakbrowser"),
        "playwright": _version("playwright"),
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/versions.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except Exception:
        return ""


def _git_commit(path: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", path, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
