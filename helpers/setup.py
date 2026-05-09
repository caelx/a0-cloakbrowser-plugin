from __future__ import annotations

import importlib.metadata
from typing import Any

from .config import apply_environment, get_config
from .dependency_install import install_python_dependencies, install_system_dependencies
from .extensions import install_configured_extensions, sync_browser_extension_paths
from .install_manifest import load_manifest, mark_setup, record_warning, save_manifest
from .playwright_shim import patch_playwright
from .runtime_patch import apply_runtime_patch
from .seed_playwright import ensure_masquerade
from .xvfb import ensure_display


def setup_plugin(*, noninteractive: bool = False, skip_system_deps: bool = False) -> dict[str, Any]:
    cfg = get_config()
    manifest = load_manifest()
    apply_environment(cfg)

    system_result = {"skipped": True}
    if not skip_system_deps:
        system_result = install_system_dependencies(noninteractive=noninteractive)
        if not system_result.get("ok"):
            record_warning(manifest, f"System dependency install incomplete: {system_result.get('reason') or system_result.get('stderr_tail', '')[:200]}")

    python_result = install_python_dependencies()
    if not python_result.get("ok"):
        record_warning(manifest, "Python dependency install failed")
        save_manifest(manifest)
        return {"ok": False, "system": system_result, "python": python_result, "manifest": manifest}

    try:
        import cloakbrowser

        binary = cloakbrowser.ensure_binary()
        manifest["cloakbrowser"] = {
            "version": importlib.metadata.version("cloakbrowser"),
            "binary_path": binary,
            "cache_path": cfg["runtime"]["cloakbrowser_cache_dir"],
        }
        masquerade = ensure_masquerade(binary)
        manifest["playwright_shim"] = {"masquerade_path": str(masquerade)}
    except Exception as exc:
        record_warning(manifest, f"CloakBrowser binary setup failed: {exc}")
        save_manifest(manifest)
        return {"ok": False, "system": system_result, "python": python_result, "error": str(exc)}

    display_result = ensure_display(cfg, manifest)
    extension_installs = install_configured_extensions(cfg, manifest)
    active_paths = sync_browser_extension_paths(cfg)
    runtime_patch = apply_runtime_patch()
    shim_patch = patch_playwright()

    mark_setup(manifest)
    save_manifest(manifest)
    return {
        "ok": True,
        "system": system_result,
        "python": python_result,
        "display": display_result,
        "extensions_installed": extension_installs,
        "active_extension_paths": active_paths,
        "runtime_patch": runtime_patch,
        "playwright_shim": shim_patch,
        "manifest": manifest,
    }
