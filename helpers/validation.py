from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import get_config
from .extensions import verify_extension_reconciliation
from .install_manifest import load_manifest
from .patcher import sha256_file
from .source_patch import (
    CLOSE_ALL_PATCHED,
    CLOSE_BROWSER_PATCHED,
    CONTEXT_CLOSED_PATCHED,
    CONTENT_HELPER_PATCHED,
    LAUNCH_PATCHED,
    OPEN_PATCHED,
    OPEN_PATCHED_WITH_LIMIT,
    PATCH_MARKER,
    PATCH_VERSION,
    SHADOW_PATCHED,
    STOP_PLAYWRIGHT_PATCHED,
    WS_CLASS_PATCHED,
    WS_INPUT_PATCHED,
    WS_PATCH_VERSION,
    browser_runtime_source_path,
    browser_ws_source_path,
)
from .xvfb import display_usable


def validate_runtime_patch(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or load_manifest()
    patch = manifest.get("runtime_source_patch") or {}
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {"manifest": patch}
    failures: list[str] = []

    try:
        target = Path(str(patch.get("target_path") or browser_runtime_source_path()))
        text = target.read_text(encoding="utf-8")
        current_hash = sha256_file(target)
    except Exception as exc:
        return _result(False, {"runtime_source_readable": False}, ["runtime_source_readable"], {"error": str(exc)})

    marker_start_count = text.count(f"# {PATCH_MARKER}: start")
    marker_end_count = text.count(f"# {PATCH_MARKER}: end")
    checks["marker_once"] = marker_start_count == 1 and marker_end_count == 1
    details["marker_start_count"] = marker_start_count
    details["marker_end_count"] = marker_end_count
    checks["patch_version_current"] = patch.get("patch_version") == PATCH_VERSION
    checks["launch_patch_present"] = LAUNCH_PATCHED in text
    checks["open_restart_patch_present"] = OPEN_PATCHED in text or OPEN_PATCHED_WITH_LIMIT in text
    checks["close_context_patch_present"] = all(
        snippet in text
        for snippet in (
            CLOSE_BROWSER_PATCHED,
            CLOSE_ALL_PATCHED,
            CONTEXT_CLOSED_PATCHED,
            STOP_PLAYWRIGHT_PATCHED,
        )
    )
    checks["shadow_or_content_patch_present"] = SHADOW_PATCHED in text or CONTENT_HELPER_PATCHED in text
    backup_path = Path(str(patch.get("backup_path") or ""))
    checks["backup_exists"] = bool(patch.get("backup_path")) and backup_path.is_file()
    checks["patched_hash_matches"] = bool(patch.get("patched_hash")) and current_hash == patch.get("patched_hash")
    original_hash = patch.get("original_hash")
    checks["original_hash_recorded"] = bool(original_hash)
    if checks["backup_exists"] and original_hash:
        checks["backup_hash_matches"] = sha256_file(backup_path) == original_hash
    else:
        checks["backup_hash_matches"] = False
    checks["upstream_not_drifted"] = checks["patched_hash_matches"]

    ws_patch = manifest.get("ws_browser_source_patch") or {}
    details["ws_manifest"] = ws_patch
    try:
        ws_target = Path(str(ws_patch.get("target_path") or browser_ws_source_path()))
        ws_text = ws_target.read_text(encoding="utf-8")
        ws_current_hash = sha256_file(ws_target)
    except Exception as exc:
        checks["ws_source_readable"] = False
        details["ws_error"] = str(exc)
    else:
        checks["ws_patch_version_current"] = ws_patch.get("patch_version") == WS_PATCH_VERSION
        checks["ws_keyboard_dedupe_present"] = WS_CLASS_PATCHED in ws_text and WS_INPUT_PATCHED in ws_text
        ws_backup_path = Path(str(ws_patch.get("backup_path") or ""))
        checks["ws_backup_exists"] = bool(ws_patch.get("backup_path")) and ws_backup_path.is_file()
        checks["ws_patched_hash_matches"] = (
            bool(ws_patch.get("patched_hash")) and ws_current_hash == ws_patch.get("patched_hash")
        )
        ws_original_hash = ws_patch.get("original_hash")
        checks["ws_original_hash_recorded"] = bool(ws_original_hash)
        if checks["ws_backup_exists"] and ws_original_hash:
            checks["ws_backup_hash_matches"] = sha256_file(ws_backup_path) == ws_original_hash
        else:
            checks["ws_backup_hash_matches"] = False
        details.update(
            {
                "ws_target_path": str(ws_target),
                "ws_current_hash": ws_current_hash,
                "ws_backup_path": str(ws_backup_path) if ws_patch.get("backup_path") else "",
            }
        )

    details.update(
        {
            "target_path": str(target),
            "current_hash": current_hash,
            "backup_path": str(backup_path) if patch.get("backup_path") else "",
        }
    )
    failures = [name for name, ok in checks.items() if not ok]
    return _result(not failures, checks, failures, details)


def collect_invariants(status: dict[str, Any] | None = None) -> dict[str, bool]:
    cfg = get_config(status.get("config") if status else None)
    manifest = load_manifest()
    runtime_validation = (
        status.get("runtime_patch_validation")
        if status and status.get("runtime_patch_validation")
        else validate_runtime_patch(manifest)
    )
    extension_validation = (
        status.get("extension_reconciliation")
        if status and status.get("extension_reconciliation")
        else verify_extension_reconciliation(cfg)
    )
    last_launch = manifest.get("last_launch") or {}
    display = status.get("display", {}) if status else {}
    cloakbrowser = status.get("cloakbrowser", {}) if status else {}
    setup = status.get("setup", {}) if status else {}
    return {
        "plugin_enabled": _plugin_enabled("cloakbrowser"),
        "runtime_enabled": bool(cfg.get("runtime", {}).get("enabled")),
        "cloakbrowser_installed": bool(cloakbrowser.get("installed")) if status else _cloakbrowser_importable(),
        "display_ready": bool(display.get("usable_current") or display.get("usable_configured"))
        if status
        else display_usable(os.environ.get("DISPLAY", "")) or display_usable(cfg["runtime"]["display"]),
        "source_patch_current": bool(runtime_validation.get("ok")),
        "extension_config_reconciled": bool(extension_validation.get("ok")),
        "last_launch_used_cloakbrowser": _last_launch_used_cloakbrowser(last_launch),
        "setup_complete": bool(setup.get("installed")) if status else manifest.get("setup_status") == "setup",
    }


def _last_launch_used_cloakbrowser(last_launch: dict[str, Any]) -> bool:
    return bool(last_launch.get("patched")) and "cloakbrowser" in str(last_launch.get("binary", "")).lower()


def _plugin_enabled(plugin_name: str) -> bool:
    try:
        from .config import _without_local_helpers, plugin_dir

        with _without_local_helpers(plugin_dir()):
            from helpers import plugins

            enabled = plugins.get_enabled_plugins(None)
        if enabled is None:
            return True
        for item in enabled:
            if item == plugin_name:
                return True
            if isinstance(item, dict):
                name = item.get("name") or item.get("id") or item.get("plugin_name")
            else:
                name = getattr(item, "name", None) or getattr(item, "id", None)
            if name == plugin_name:
                return True
    except Exception:
        return True
    return False


def _cloakbrowser_importable() -> bool:
    try:
        import cloakbrowser  # noqa: F401
    except Exception:
        return False
    return True


def _result(ok: bool, checks: dict[str, bool], failures: list[str], details: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": ok,
        "checks": checks,
        "failed": failures,
        "details": _jsonable(details),
    }


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)
