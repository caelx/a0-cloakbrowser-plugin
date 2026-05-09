from __future__ import annotations

import shutil

from .extensions import disable_managed_extension_paths, managed_extension_paths
from .install_manifest import load_manifest, save_manifest
from .runtime_patch import unpatch_runtime
from .playwright_shim import unpatch_playwright
from .seed_playwright import remove_masquerade
from .xvfb import remove_supervisor_config_if_owned


def uninstall(*, remove_extensions: bool = False) -> dict:
    manifest = load_manifest()
    disabled_paths = disable_managed_extension_paths()
    runtime = unpatch_runtime()
    shim = unpatch_playwright()
    masquerade_removed = remove_masquerade(
        manifest.get("playwright_shim", {}).get("masquerade_path") or None
    )
    supervisor = remove_supervisor_config_if_owned(manifest)
    removed_extensions: list[str] = []
    if remove_extensions:
        for path in managed_extension_paths().values():
            if path.exists():
                shutil.rmtree(path)
                removed_extensions.append(str(path))
    manifest["setup_status"] = "uninstalled"
    save_manifest(manifest)
    return {
        "ok": True,
        "disabled_extension_paths": disabled_paths,
        "runtime_patch": runtime,
        "playwright_shim": shim,
        "masquerade_removed": masquerade_removed,
        "supervisor": supervisor,
        "removed_extensions": removed_extensions,
        "restart_required": True,
    }
