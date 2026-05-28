from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .config import manifest_path

PLUGIN_VERSION = "1.3.14"


def empty_manifest() -> dict[str, Any]:
    return {
        "plugin_version": PLUGIN_VERSION,
        "setup_status": "not_setup",
        "setup_timestamp": "",
        "agent_zero": {},
        "runtime_patches": [],
        "runtime_patch_validation": {},
        "extension_reconciliation": {},
        "launch_verification": {},
        "last_launch": {},
        "last_repair_status": "",
        "last_repair_error": "",
        "playwright_shim": {},
        "xvfb": {},
        "display": "",
        "extensions": {},
        "cloakbrowser": {},
        "warnings": [],
    }


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    target = path or manifest_path()
    if not target.is_file():
        return empty_manifest()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return empty_manifest()
    manifest = empty_manifest()
    manifest.update(data if isinstance(data, dict) else {})
    return manifest


def save_manifest(manifest: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    target = path or manifest_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def mark_setup(manifest: dict[str, Any]) -> dict[str, Any]:
    manifest["plugin_version"] = PLUGIN_VERSION
    manifest["setup_status"] = "setup"
    manifest["setup_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return manifest


def record_extension(manifest: dict[str, Any], key: str, payload: dict[str, Any]) -> None:
    manifest.setdefault("extensions", {})[key] = payload


def record_warning(manifest: dict[str, Any], warning: str) -> None:
    warnings = manifest.setdefault("warnings", [])
    if warning not in warnings:
        warnings.append(warning)
