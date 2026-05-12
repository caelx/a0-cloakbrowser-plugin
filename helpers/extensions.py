from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
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
    if ext["enable_i_still_dont_care_about_cookies"] and _is_loadable(
        paths["i_still_dont_care_about_cookies"]
    ):
        active.append(str(paths["i_still_dont_care_about_cookies"]))
    if ext["enable_bypass_paywalls_clean"] and _is_loadable(paths["bypass_paywalls_clean"]):
        active.append(str(paths["bypass_paywalls_clean"]))
    return active


def install_configured_extensions(
    config: dict[str, Any] | None, manifest: dict[str, Any]
) -> list[str]:
    cfg = get_config(config)
    paths = managed_extension_paths()
    ext = cfg["extensions"]
    installed: list[str] = []
    actions: list[dict[str, Any]] = []

    if ext["enable_ublock_origin_lite"]:
        action = "updated" if _is_loadable(paths["ublock_origin_lite"]) else "installed"
        meta = install_ublock_origin_lite(paths["ublock_origin_lite"], cfg["ublock_origin_lite"])
        record_extension(manifest, "ublock_origin_lite", meta)
        installed.append("ublock_origin_lite")
        actions.append(
            _extension_action("ublock_origin_lite", paths["ublock_origin_lite"], action, cfg)
        )
    elif _is_loadable(paths["ublock_origin_lite"]):
        record_extension(
            manifest,
            "ublock_origin_lite",
            extension_metadata(paths["ublock_origin_lite"], source="existing"),
        )
        actions.append(
            _extension_action("ublock_origin_lite", paths["ublock_origin_lite"], "reused", cfg)
        )
    else:
        actions.append(
            _extension_action("ublock_origin_lite", paths["ublock_origin_lite"], "skipped", cfg)
        )

    if ext["enable_i_still_dont_care_about_cookies"]:
        action = (
            "updated" if _is_loadable(paths["i_still_dont_care_about_cookies"]) else "installed"
        )
        meta = install_chrome_web_store_extension(
            COOKIE_EXTENSION_ID,
            paths["i_still_dont_care_about_cookies"],
        )
        record_extension(manifest, "i_still_dont_care_about_cookies", meta)
        installed.append("i_still_dont_care_about_cookies")
        actions.append(
            _extension_action(
                "i_still_dont_care_about_cookies",
                paths["i_still_dont_care_about_cookies"],
                action,
                cfg,
            )
        )
    elif _is_loadable(paths["i_still_dont_care_about_cookies"]):
        record_extension(
            manifest,
            "i_still_dont_care_about_cookies",
            extension_metadata(paths["i_still_dont_care_about_cookies"], source="existing"),
        )
        actions.append(
            _extension_action(
                "i_still_dont_care_about_cookies",
                paths["i_still_dont_care_about_cookies"],
                "reused",
                cfg,
            )
        )
    else:
        actions.append(
            _extension_action(
                "i_still_dont_care_about_cookies",
                paths["i_still_dont_care_about_cookies"],
                "skipped",
                cfg,
            )
        )

    if ext["enable_bypass_paywalls_clean"]:
        action = "updated" if _is_loadable(paths["bypass_paywalls_clean"]) else "installed"
        meta = install_bypass_paywalls_clean(
            paths["bypass_paywalls_clean"], config=cfg["bypass_paywalls_clean"]
        )
        record_extension(manifest, "bypass_paywalls_clean", meta)
        installed.append("bypass_paywalls_clean")
        actions.append(
            _extension_action("bypass_paywalls_clean", paths["bypass_paywalls_clean"], action, cfg)
        )
    elif _is_loadable(paths["bypass_paywalls_clean"]):
        record_extension(
            manifest,
            "bypass_paywalls_clean",
            extension_metadata(paths["bypass_paywalls_clean"], source="existing"),
        )
        actions.append(
            _extension_action(
                "bypass_paywalls_clean", paths["bypass_paywalls_clean"], "reused", cfg
            )
        )
    else:
        actions.append(
            _extension_action(
                "bypass_paywalls_clean", paths["bypass_paywalls_clean"], "skipped", cfg
            )
        )

    manifest["extension_paths_enabled"] = active_extension_paths(cfg)
    manifest["extension_actions"] = actions
    sync_browser_extension_paths(cfg)
    return installed


def sync_browser_extension_paths(config: dict[str, Any] | None = None) -> list[str]:
    active = active_extension_paths(config)
    with _agent_zero_browser_config_context() as (plugins, get_browser_config):
        browser_config = get_browser_config()
        current_paths = [
            str(Path(path).expanduser()) for path in browser_config.get("extension_paths", [])
        ]
        managed = managed_extension_paths()
        preserved = [
            path for path in current_paths if not _is_managed_extension_path(path, managed)
        ]
        browser_config["extension_paths"] = _dedupe_paths(
            preserved + [path for path in active if path not in preserved]
        )
        plugins.save_plugin_config("_browser", "", "", browser_config)
    return active


def disable_managed_extension_paths() -> list[str]:
    removed: list[str] = []
    with _agent_zero_browser_config_context() as (plugins, get_browser_config):
        managed = managed_extension_paths()
        browser_config = get_browser_config()
        paths = []
        for path in browser_config.get("extension_paths", []):
            normalized = str(Path(path).expanduser())
            if _is_managed_extension_path(normalized, managed):
                removed.append(normalized)
                continue
            paths.append(path)
        browser_config["extension_paths"] = paths
        plugins.save_plugin_config("_browser", "", "", browser_config)
    return removed


@contextmanager
def _agent_zero_browser_config_context():
    from .runtime_patch import _agent_zero_import_context

    with _agent_zero_import_context():
        yield _browser_config_helpers()


def _browser_config_helpers():
    from helpers import plugins
    from plugins._browser.helpers.config import get_browser_config

    return plugins, get_browser_config


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


def _is_managed_extension_path(path: str, managed: dict[str, Path]) -> bool:
    candidate = Path(path).expanduser()
    if str(candidate) in {str(item) for item in managed.values()}:
        return True
    parts = candidate.parts
    names = {item.name for item in managed.values()}
    return (
        candidate.name in names
        and len(parts) >= 3
        and any(
            parts[index : index + 2] == (".cloakbrowser", "extensions")
            for index in range(len(parts) - 1)
        )
    )


def _dedupe_paths(paths) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for path in paths:
        text = str(path)
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _extension_action(key: str, path: Path, action: str, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "name": EXTENSION_KEYS[key],
        "path": str(path),
        "action": action,
        "installed": _is_loadable(path),
        "enabled": str(path) in set(active_extension_paths(config)),
    }
