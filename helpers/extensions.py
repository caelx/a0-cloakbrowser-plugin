from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .bypass_paywalls_clean import install_bypass_paywalls_clean
from .chrome_store import extension_metadata, install_chrome_web_store_extension
from .config import COOKIE_EXTENSION_ID, extension_root, get_config
from .install_manifest import record_extension
from .ubol import install_ublock_origin_lite

EXTENSION_KEYS = {
    "ublock_origin_lite": "uBlock Origin Lite",
    "i_still_dont_care_about_cookies": "I still don't care about cookies",
    "bypass_paywalls_clean": "Bypass Paywalls Clean",
}


def managed_extension_paths() -> dict[str, Path]:
    root = extension_root()
    return {
        "ublock_origin_lite": root / "ublock-origin-lite",
        "i_still_dont_care_about_cookies": root / "i-still-dont-care-about-cookies",
        "bypass_paywalls_clean": root / "bypass-paywalls-clean",
    }


def active_extension_paths(config: dict[str, Any] | None = None) -> list[str]:
    cfg = get_config(config)
    paths = managed_extension_paths()
    ext = cfg["extensions"]
    active: list[str] = []
    if ext["enable_ublock_origin_lite"] and _is_loadable(paths["ublock_origin_lite"]):
        active.append(str(paths["ublock_origin_lite"]))
    if ext["enable_i_still_dont_care_about_cookies"] and _is_loadable(paths["i_still_dont_care_about_cookies"]):
        active.append(str(paths["i_still_dont_care_about_cookies"]))
    if ext["enable_bypass_paywalls_clean"] and _is_loadable(paths["bypass_paywalls_clean"]):
        active.append(str(paths["bypass_paywalls_clean"]))
    return active


def install_configured_extensions(config: dict[str, Any] | None, manifest: dict[str, Any]) -> list[str]:
    cfg = get_config(config)
    paths = managed_extension_paths()
    ext = cfg["extensions"]
    installed: list[str] = []

    if ext["install_ublock_origin_lite"] and (
        ext["update_ublock_origin_lite_on_setup"] or not _is_loadable(paths["ublock_origin_lite"])
    ):
        meta = install_ublock_origin_lite(paths["ublock_origin_lite"], cfg["ublock_origin_lite"])
        record_extension(manifest, "ublock_origin_lite", meta)
        installed.append("ublock_origin_lite")
    elif _is_loadable(paths["ublock_origin_lite"]):
        record_extension(manifest, "ublock_origin_lite", extension_metadata(paths["ublock_origin_lite"], source="existing"))

    if ext["install_i_still_dont_care_about_cookies"] and (
        ext["update_i_still_dont_care_about_cookies_on_setup"]
        or not _is_loadable(paths["i_still_dont_care_about_cookies"])
    ):
        meta = install_chrome_web_store_extension(
            COOKIE_EXTENSION_ID,
            paths["i_still_dont_care_about_cookies"],
        )
        record_extension(manifest, "i_still_dont_care_about_cookies", meta)
        installed.append("i_still_dont_care_about_cookies")
    elif _is_loadable(paths["i_still_dont_care_about_cookies"]):
        record_extension(
            manifest,
            "i_still_dont_care_about_cookies",
            extension_metadata(paths["i_still_dont_care_about_cookies"], source="existing"),
        )

    if ext["install_bypass_paywalls_clean"] and (
        ext["update_bypass_paywalls_clean_on_setup"] or not _is_loadable(paths["bypass_paywalls_clean"])
    ):
        meta = install_bypass_paywalls_clean(paths["bypass_paywalls_clean"])
        record_extension(manifest, "bypass_paywalls_clean", meta)
        installed.append("bypass_paywalls_clean")
    elif _is_loadable(paths["bypass_paywalls_clean"]):
        record_extension(
            manifest,
            "bypass_paywalls_clean",
            extension_metadata(paths["bypass_paywalls_clean"], source="existing"),
        )

    manifest["extension_paths_enabled"] = active_extension_paths(cfg)
    sync_browser_extension_paths(cfg)
    return installed


def sync_browser_extension_paths(config: dict[str, Any] | None = None) -> list[str]:
    active = active_extension_paths(config)
    try:
        from helpers import plugins
        from plugins._browser.helpers.config import get_browser_config

        browser_config = get_browser_config()
        current_paths = [str(Path(path).expanduser()) for path in browser_config.get("extension_paths", [])]
        managed = {str(path) for path in managed_extension_paths().values()}
        preserved = [path for path in current_paths if path not in managed]
        browser_config["extension_paths"] = preserved + [path for path in active if path not in preserved]
        plugins.save_plugin_config("_browser", "", "", browser_config)
    except Exception:
        pass
    return active


def disable_managed_extension_paths() -> list[str]:
    removed: list[str] = []
    try:
        from helpers import plugins
        from plugins._browser.helpers.config import get_browser_config

        managed = {str(path) for path in managed_extension_paths().values()}
        browser_config = get_browser_config()
        paths = []
        for path in browser_config.get("extension_paths", []):
            normalized = str(Path(path).expanduser())
            if normalized in managed:
                removed.append(normalized)
                continue
            paths.append(path)
        browser_config["extension_paths"] = paths
        plugins.save_plugin_config("_browser", "", "", browser_config)
    except Exception:
        pass
    return removed


def list_extension_status(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = get_config(config)
    active = set(active_extension_paths(cfg))
    out: list[dict[str, Any]] = []
    for key, path in managed_extension_paths().items():
        manifest_path = path / "manifest.json"
        manifest: dict[str, Any] = {}
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        out.append(
            {
                "key": key,
                "name": EXTENSION_KEYS[key],
                "path": str(path),
                "installed": manifest_path.is_file(),
                "enabled": str(path) in active,
                "manifest_name": manifest.get("name") or "",
                "manifest_version": manifest.get("version") or "",
                "permissions": manifest.get("permissions") or [],
                "host_permissions": manifest.get("host_permissions") or [],
            }
        )
    return out


def uninstall_managed_extension(key: str, *, remove_files: bool = False) -> dict[str, Any]:
    paths = managed_extension_paths()
    if key not in paths:
        raise ValueError(f"Unknown extension key: {key}")
    disable_managed_extension_paths()
    path = paths[key]
    removed = False
    if remove_files and path.exists():
        shutil.rmtree(path)
        removed = True
    return {"key": key, "path": str(path), "removed_files": removed}


def _is_loadable(path: Path) -> bool:
    return (path / "manifest.json").is_file()
