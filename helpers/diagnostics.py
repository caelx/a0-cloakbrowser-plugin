from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import get_config, redacted_config
from .extensions import active_extension_paths, list_extension_status
from .install_manifest import load_manifest
from .playwright_shim import status as shim_status
from .runtime_patch import status as runtime_patch_status
from .xvfb import display_usable


def collect_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = get_config(config)
    return {
        "ok": True,
        "plugin": "cloakbrowser",
        "config": redacted_config(cfg),
        "manifest": load_manifest(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "display": os.environ.get("DISPLAY", ""),
            "xdpyinfo": bool(shutil.which("xdpyinfo")),
            "xvfb": bool(shutil.which("Xvfb")),
            "supervisorctl": bool(shutil.which("supervisorctl")),
        },
        "display": {
            "configured": cfg["runtime"]["display"],
            "current": os.environ.get("DISPLAY", ""),
            "usable_configured": display_usable(cfg["runtime"]["display"]),
            "usable_current": display_usable(os.environ.get("DISPLAY", "")),
        },
        "cloakbrowser": cloakbrowser_status(),
        "patches": {
            "playwright_shim": shim_status(),
            "runtime_patch": runtime_patch_status(),
        },
        "extensions": {
            "active_paths": active_extension_paths(cfg),
            "items": list_extension_status(cfg),
        },
        "browser": browser_status(),
    }


def cloakbrowser_status() -> dict[str, Any]:
    try:
        mod = importlib.import_module("cloakbrowser")
    except Exception as exc:
        return {"installed": False, "error": str(exc)}
    out: dict[str, Any] = {
        "installed": True,
        "version": getattr(mod, "__version__", ""),
    }
    try:
        out["binary_path"] = mod.ensure_binary()
    except Exception as exc:
        out["binary_error"] = str(exc)
    try:
        from cloakbrowser import binary_info

        out["binary_info"] = binary_info()
    except Exception as exc:
        out["binary_info_error"] = str(exc)
    return out


def browser_status() -> dict[str, Any]:
    try:
        from .runtime_patch import _agent_zero_import_context

        with _agent_zero_import_context():
            from helpers import plugins
            from plugins._browser.helpers.config import build_browser_launch_config, get_browser_config

            enabled = "_browser" in plugins.get_enabled_plugins(None)
            browser_config = get_browser_config()
            launch_config = build_browser_launch_config(browser_config)
        return {
            "upstream_available": True,
            "builtin_browser_enabled": enabled,
            "extension_paths": browser_config.get("extension_paths", []),
            "launch_args": launch_config.get("args", []),
        }
    except Exception as exc:
        return {"upstream_available": False, "error": str(exc)}
