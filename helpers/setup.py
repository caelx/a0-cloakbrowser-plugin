from __future__ import annotations

import importlib.metadata
import shutil
import copy
from typing import Any

from .config import apply_environment, get_config
from .dependency_install import install_python_dependencies, install_system_dependencies
from .extensions import disable_managed_extension_paths, install_configured_extensions, managed_extension_paths, sync_browser_extension_paths
from .install_manifest import load_manifest, mark_setup, record_warning, save_manifest
from .seed_playwright import ensure_masquerade, remove_masquerade
from .xvfb import ensure_display, remove_direct_xvfb_if_owned, remove_supervisor_config_if_owned


def setup_plugin(*, noninteractive: bool = False, skip_system_deps: bool = False) -> dict[str, Any]:
    cfg = get_config()
    previous_manifest = load_manifest()
    manifest = copy.deepcopy(previous_manifest)
    apply_environment(cfg)

    system_result = {"skipped": True}
    if not skip_system_deps:
        system_result = install_system_dependencies(noninteractive=noninteractive)
        if not system_result.get("ok"):
            record_warning(manifest, f"System dependency install incomplete: {system_result.get('reason') or system_result.get('stderr_tail', '')[:200]}")

    python_result = install_python_dependencies()
    if not python_result.get("ok"):
        record_warning(manifest, "Python dependency install failed")
        manifest["setup_status"] = "failed"
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
        manifest["playwright_shim"] = {
            "masquerade_path": str(masquerade),
            "masquerade_target": binary,
            "patching": "process-local",
            "persistent_runtime_patch": False,
        }
    except Exception as exc:
        record_warning(manifest, f"CloakBrowser binary setup failed: {exc}")
        manifest["setup_status"] = "failed"
        save_manifest(manifest)
        return {"ok": False, "system": system_result, "python": python_result, "error": str(exc), "manifest": manifest}

    try:
        display_result = ensure_display(cfg, manifest)
        extension_installs = install_configured_extensions(cfg, manifest)
        active_paths = sync_browser_extension_paths(cfg)
    except Exception as exc:
        record_warning(manifest, f"Setup failed after dependency install: {exc}")
        rollback = _rollback_failed_setup(manifest, previous_manifest=previous_manifest)
        save_manifest(manifest)
        return {
            "ok": False,
            "system": system_result,
            "python": python_result,
            "error": str(exc),
            "rollback": rollback,
            "manifest": manifest,
        }
    runtime_patch = {
        "patching": "process-local",
        "persistent": False,
        "applied_in_setup": False,
        "applies_when": "Browser tool execution or smoke test process",
    }
    shim_patch = {
        "patching": "process-local",
        "persistent": False,
        "applied_in_setup": False,
        "applies_when": "Browser tool execution or smoke test process",
    }

    mark_setup(manifest)
    save_manifest(manifest)
    return {
        "ok": True,
        "system": system_result,
        "python": python_result,
        "display": display_result,
        "extensions_installed": extension_installs,
        "extension_actions": manifest.get("extension_actions", []),
        "active_extension_paths": active_paths,
        "runtime_patch": runtime_patch,
        "playwright_shim": shim_patch,
        "manifest": manifest,
    }


def _rollback_failed_setup(
    manifest: dict[str, Any],
    *,
    previous_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_manifest = previous_manifest or {}
    preserve_prior_setup = previous_manifest.get("setup_status") == "setup"
    removed_extension_paths = []
    if not preserve_prior_setup:
        for path in managed_extension_paths().values():
            if path.exists() and not (path / "manifest.json").is_file():
                shutil.rmtree(path)
                removed_extension_paths.append(str(path))
    rollback = {
        "disabled_extension_paths": [] if preserve_prior_setup else disable_managed_extension_paths(),
        "masquerade_removed": False
        if preserve_prior_setup
        else remove_masquerade(
            manifest.get("playwright_shim", {}).get("masquerade_path") or None,
        ),
        "supervisor": {"removed": "", "preserved_prior_setup": True}
        if preserve_prior_setup
        else remove_supervisor_config_if_owned(manifest),
        "direct_xvfb": {"removed": False, "preserved_prior_setup": True}
        if preserve_prior_setup
        else remove_direct_xvfb_if_owned(manifest),
        "removed_incomplete_extensions": removed_extension_paths,
        "preserved_prior_setup": preserve_prior_setup,
        "shared_dependencies_removed": False,
    }
    manifest["setup_status"] = "failed"
    manifest["rollback"] = rollback
    return rollback
