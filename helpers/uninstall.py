from __future__ import annotations

import shutil

from .extensions import disable_managed_extension_paths, managed_extension_paths
from .install_manifest import load_manifest, save_manifest
from .runtime_patch import unpatch_runtime
from .playwright_shim import unpatch_playwright
from .seed_playwright import remove_masquerade
from .source_patch import restore_runtime_source_patch, restore_ws_browser_source_patch
from .xvfb import remove_direct_xvfb_if_owned, remove_supervisor_config_if_owned


def uninstall(*, remove_extensions: bool = False) -> dict:
    manifest = load_manifest()
    disabled_paths = disable_managed_extension_paths()
    runtime = unpatch_runtime()
    shim = unpatch_playwright()
    source_patch = restore_runtime_source_patch(manifest)
    ws_source_patch = restore_ws_browser_source_patch(manifest)
    masquerade_removed = remove_masquerade(
        manifest.get("playwright_shim", {}).get("masquerade_path") or None
    )
    supervisor = remove_supervisor_config_if_owned(manifest)
    direct_xvfb = remove_direct_xvfb_if_owned(manifest)
    removed_extensions: list[str] = []
    if remove_extensions:
        for path in managed_extension_paths().values():
            if path.exists():
                shutil.rmtree(path)
                removed_extensions.append(str(path))
    manifest["setup_status"] = "uninstalled"
    manifest["runtime_source_restore"] = source_patch
    manifest["ws_browser_source_restore"] = ws_source_patch
    save_manifest(manifest)
    ok = (
        source_patch.get("restored") is True
        or source_patch.get("reason") == "not_patched"
    ) and (
        ws_source_patch.get("restored") is True
        or ws_source_patch.get("reason") == "not_patched"
    )
    return {
        "ok": ok,
        "disabled_extension_paths": disabled_paths,
        "runtime_patch": runtime,
        "runtime_source_patch": source_patch,
        "ws_browser_source_patch": ws_source_patch,
        "playwright_shim": shim,
        "masquerade_removed": masquerade_removed,
        "supervisor": supervisor,
        "direct_xvfb": direct_xvfb,
        "removed_extensions": removed_extensions,
        "restart_required": False,
    }
