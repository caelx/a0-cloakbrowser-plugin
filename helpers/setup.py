from __future__ import annotations

import importlib.metadata
import contextlib
import shutil
import copy
import io
from typing import Any

from .config import apply_environment, get_config
from .dependency_install import install_python_dependencies, install_system_dependencies
from .extensions import (
    disable_managed_extension_paths,
    install_configured_extensions,
    managed_extension_paths,
    sync_browser_extension_paths,
    verify_extension_reconciliation,
)
from .install_manifest import load_manifest, mark_setup, record_warning, save_manifest
from .lifecycle import reconcile_after_setup
from .seed_playwright import ensure_masquerade, remove_masquerade
from .source_patch import patch_browser_store_source, patch_runtime_source, patch_ws_browser_source
from .validation import validate_runtime_patch
from .verify import verify_browser_launch
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
            record_warning(
                manifest,
                f"System dependency install incomplete: {system_result.get('reason') or system_result.get('stderr_tail', '')[:200]}",
            )

    python_result = install_python_dependencies(
        auto_update_cloakbrowser=cfg.get("runtime", {}).get("cloakbrowser_auto_update", True),
        repair_playwright=True,
    )
    if not python_result.get("ok"):
        record_warning(manifest, "Python dependency install failed")
        _mark_setup_failure(manifest, previous_manifest=previous_manifest, error="Python dependency install failed")
        save_manifest(manifest)
        return {"ok": False, "system": system_result, "python": python_result, "manifest": manifest}

    try:
        with contextlib.redirect_stdout(io.StringIO()):
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
        _mark_setup_failure(manifest, previous_manifest=previous_manifest, error=str(exc))
        save_manifest(manifest)
        return {
            "ok": False,
            "system": system_result,
            "python": python_result,
            "error": str(exc),
            "manifest": manifest,
        }

    try:
        display_result = ensure_display(cfg, manifest)
        extension_installs = install_configured_extensions(cfg, manifest)
        active_paths = sync_browser_extension_paths(cfg)
        extension_validation = verify_extension_reconciliation(cfg)
        if not extension_validation.get("ok"):
            raise RuntimeError(
                "Extension reconciliation failed: "
                + ", ".join(extension_validation.get("failed") or ["unknown"])
            )
        source_patch = patch_runtime_source(manifest)
        ws_source_patch = patch_ws_browser_source(manifest)
        browser_store_source_patch = patch_browser_store_source(manifest)
        runtime_validation = validate_runtime_patch(manifest)
        if not runtime_validation.get("ok"):
            raise RuntimeError(
                "Required runtime patch failed: "
                + ", ".join(runtime_validation.get("failed") or ["unknown"])
            )
        manifest["extension_reconciliation"] = extension_validation
        manifest["runtime_patch_validation"] = runtime_validation
        save_manifest(manifest)
        lifecycle = reconcile_after_setup(
            cfg,
            {
                "applied": bool(
                    source_patch.get("applied")
                    or ws_source_patch.get("applied")
                    or browser_store_source_patch.get("applied")
                ),
                "already_patched": bool(
                    source_patch.get("already_patched") and ws_source_patch.get("already_patched")
                    and browser_store_source_patch.get("already_patched")
                ),
            },
        )
        manifest["lifecycle"] = lifecycle
        restart = lifecycle.get("agent_zero_restart") or {}
        if restart.get("scheduled"):
            launch_verification = {
                "ok": True,
                "skipped": True,
                "reason": "assumed_ready_after_agent_zero_restart",
                "message": restart.get("message", "Agent Zero restart scheduled after Execute returns."),
            }
            manifest["launch_verification"] = launch_verification
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
                "extension_reconciliation": extension_validation,
                "runtime_patch_validation": runtime_validation,
                "launch_verification": launch_verification,
                "lifecycle": lifecycle,
                "restart_scheduled": True,
                "restart_message": restart.get("message", ""),
                "manifest": manifest,
            }
        if lifecycle.get("restart_required"):
            reason = restart.get("reason") or "agent_zero_restart_required"
            raise RuntimeError(f"Agent Zero restart required after runtime patch: {reason}")
        save_manifest(manifest)
        launch_verification = verify_browser_launch()
        manifest = load_manifest()
        manifest["lifecycle"] = lifecycle
        manifest["launch_verification"] = launch_verification
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
        "patching": "source-bootstrap",
        "persistent": True,
        "applied_in_setup": bool(source_patch.get("applied")),
        "source_patch": source_patch,
        "ws_source_patch": ws_source_patch,
        "browser_store_source_patch": browser_store_source_patch,
        "applies_when": "Agent Zero _browser runtime import and Browser launch",
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
        "extension_reconciliation": extension_validation,
        "runtime_patch_validation": runtime_validation,
        "launch_verification": launch_verification,
        "lifecycle": lifecycle,
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
        "disabled_extension_paths": []
        if preserve_prior_setup
        else disable_managed_extension_paths(),
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
    _mark_setup_failure(
        manifest,
        previous_manifest=previous_manifest,
        error=str(manifest.get("warnings", ["setup failed"])[-1]),
    )
    manifest["rollback"] = rollback
    return rollback


def _mark_setup_failure(
    manifest: dict[str, Any],
    *,
    previous_manifest: dict[str, Any] | None,
    error: str,
) -> None:
    if (previous_manifest or {}).get("setup_status") == "setup":
        manifest["setup_status"] = "setup"
        manifest["last_repair_status"] = "failed"
        manifest["last_repair_error"] = error
        return
    manifest["setup_status"] = "failed"
    manifest["last_repair_status"] = "failed"
    manifest["last_repair_error"] = error
