from __future__ import annotations

import importlib
import contextlib
import io
import os
import platform
import shutil
from typing import Any

from .config import get_config, redacted_config
from .extensions import active_extension_paths, list_extension_status
from .install_manifest import load_manifest
from .lifecycle import inspect_live_browser_state
from .playwright_shim import status as shim_status
from .runtime_patch import status as runtime_patch_status
from .validation import collect_invariants, validate_runtime_patch
from .extensions import verify_extension_reconciliation
from .xvfb import display_usable


def collect_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = get_config(config)
    manifest = load_manifest()
    try:
        runtime_validation = validate_runtime_patch(manifest)
    except Exception as exc:
        runtime_validation = {"ok": False, "failed": ["runtime_patch_validation"], "error": str(exc)}
    try:
        extension_validation = verify_extension_reconciliation(cfg)
    except Exception as exc:
        extension_validation = {"ok": False, "failed": ["extension_reconciliation"], "error": str(exc)}
    status = {
        "ok": True,
        "plugin": "cloakbrowser",
        "config": redacted_config(cfg),
        "manifest": manifest,
        "setup": {
            "installed": manifest.get("setup_status") == "setup",
            "status": manifest.get("setup_status", "not_setup"),
            "timestamp": manifest.get("setup_timestamp", ""),
            "playwright_masquerade": manifest.get("playwright_shim", {}),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "display": os.environ.get("DISPLAY", ""),
            "xdpyinfo": bool(shutil.which("xdpyinfo")),
            "xvfb": bool(shutil.which("Xvfb")),
            "supervisorctl": bool(shutil.which("supervisorctl")),
            "shared_memory": shared_memory_status(),
        },
        "display": {
            "configured": cfg["runtime"]["display"],
            "current": os.environ.get("DISPLAY", ""),
            "usable_configured": display_usable(cfg["runtime"]["display"]),
            "usable_current": display_usable(os.environ.get("DISPLAY", "")),
        },
        "cloakbrowser": cloakbrowser_status(),
        "patches": {
            "runtime_source_patch": manifest.get("runtime_source_patch", {}),
            "playwright_shim": {
                **shim_status(),
                "setup_installed": bool(manifest.get("playwright_shim", {}).get("masquerade_path")),
            },
            "runtime_patch": {
                **runtime_patch_status(),
                "setup_installed": bool(manifest.get("runtime_source_patch", {}).get("applied")),
            },
            "note": (
                "CloakBrowser uses a removable _browser runtime source bootstrap for "
                "Browser launches. Process-local patches are supplemental only."
            ),
            "arg_filtering": "always_on",
        },
        "effective_location": manifest.get("effective_location", {}),
        "last_launch": manifest.get("last_launch", {}),
        "runtime_patch_validation": runtime_validation,
        "extension_reconciliation": extension_validation,
        "launch_verification": manifest.get("launch_verification", {}),
        "live_browser_state": inspect_live_browser_state(cfg),
        "extensions": {
            "active_paths": active_extension_paths(cfg),
            "items": list_extension_status(cfg),
        },
        "browser": browser_status(),
    }
    status["invariants"] = collect_invariants(status)
    status["ok"] = all(status["invariants"].values())
    return status


def cloakbrowser_status() -> dict[str, Any]:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mod = importlib.import_module("cloakbrowser")
    except Exception as exc:
        return {"installed": False, "error": str(exc)}
    out: dict[str, Any] = {
        "installed": True,
        "version": getattr(mod, "__version__", ""),
    }
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            out["binary_path"] = mod.ensure_binary()
    except Exception as exc:
        out["binary_error"] = str(exc)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from cloakbrowser import binary_info

            out["binary_info"] = binary_info()
    except Exception as exc:
        out["binary_info_error"] = str(exc)
    return out


def browser_status() -> dict[str, Any]:
    try:
        from .runtime_patch import _agent_zero_import_context
        from .extensions import _load_browser_config

        with _agent_zero_import_context():
            from plugins._browser.helpers.config import (
                build_browser_launch_config,
            )

            browser_config = _load_browser_config()
            launch_config = build_browser_launch_config(browser_config)
        return {
            "upstream_available": True,
            "builtin_browser_enabled": True,
            "extension_paths": browser_config.get("extension_paths", []),
            "launch_args": launch_config.get("args", []),
        }
    except Exception as exc:
        return {"upstream_available": False, "error": str(exc)}


def shared_memory_status(path: str = "/dev/shm") -> dict[str, Any]:
    try:
        stats = os.statvfs(path)
    except OSError as exc:
        return {"path": path, "available": False, "error": str(exc)}
    total = stats.f_frsize * stats.f_blocks
    free = stats.f_frsize * stats.f_bavail
    return {
        "path": path,
        "available": True,
        "total_bytes": total,
        "free_bytes": free,
        "total_mb": round(total / 1024 / 1024, 1),
        "free_mb": round(free / 1024 / 1024, 1),
    }
