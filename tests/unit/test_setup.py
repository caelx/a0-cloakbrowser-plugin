import sys
import types

from helpers import setup


def test_successful_setup_reconciles_browser_lifecycle(monkeypatch, tmp_path):
    cloakbrowser = types.ModuleType("cloakbrowser")
    cloakbrowser.ensure_binary = lambda: "/bin/cloakbrowser"
    monkeypatch.setitem(sys.modules, "cloakbrowser", cloakbrowser)
    monkeypatch.setattr(setup.importlib.metadata, "version", lambda name: "1.0.0")
    monkeypatch.setattr(
        setup,
        "get_config",
        lambda: {"runtime": {"cloakbrowser_cache_dir": "/tmp/cache"}, "extensions": {}},
    )
    monkeypatch.setattr(setup, "apply_environment", lambda cfg: None)
    monkeypatch.setattr(setup, "load_manifest", lambda: {})
    monkeypatch.setattr(setup, "save_manifest", lambda manifest: manifest)
    monkeypatch.setattr(setup, "install_system_dependencies", lambda noninteractive: {"ok": True})
    monkeypatch.setattr(setup, "install_python_dependencies", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(setup, "ensure_masquerade", lambda binary: tmp_path / "chrome")
    monkeypatch.setattr(
        setup, "ensure_display", lambda cfg, manifest: {"ok": True, "display": ":99"}
    )
    monkeypatch.setattr(setup, "install_configured_extensions", lambda cfg, manifest: [])
    monkeypatch.setattr(setup, "sync_browser_extension_paths", lambda cfg: [])
    monkeypatch.setattr(
        setup,
        "patch_runtime_source",
        lambda manifest: {"applied": True, "already_patched": False},
    )
    monkeypatch.setattr(
        setup,
        "patch_ws_browser_source",
        lambda manifest: {"applied": True, "already_patched": False},
    )
    monkeypatch.setattr(
        setup,
        "patch_browser_store_source",
        lambda manifest: {"applied": True, "already_patched": False},
    )
    monkeypatch.setattr(setup, "verify_extension_reconciliation", lambda cfg: {"ok": True})
    monkeypatch.setattr(setup, "validate_runtime_patch", lambda manifest: {"ok": True})
    order = []
    monkeypatch.setattr(
        setup,
        "verify_browser_launch",
        lambda: order.append("verify") or {"ok": True},
    )
    lifecycle_calls = []
    monkeypatch.setattr(
        setup,
        "reconcile_after_setup",
        lambda cfg, source_patch: order.append("lifecycle")
        or lifecycle_calls.append((cfg, source_patch))
        or {
            "browser_processes_stopped": {"matched": []},
            "agent_zero_restart": {"needed": True, "restarted": True},
            "restart_required": False,
        },
    )

    result = setup.setup_plugin(noninteractive=True)

    assert result["ok"] is True
    assert order == ["lifecycle", "verify"]
    assert result["lifecycle"]["agent_zero_restart"]["restarted"] is True
    assert lifecycle_calls == [
        (
            {"runtime": {"cloakbrowser_cache_dir": "/tmp/cache"}, "extensions": {}},
            {"applied": True, "already_patched": False},
        )
    ]


def test_setup_fails_when_agent_zero_restart_is_still_required(monkeypatch, tmp_path):
    cloakbrowser = types.ModuleType("cloakbrowser")
    cloakbrowser.ensure_binary = lambda: "/bin/cloakbrowser"
    monkeypatch.setitem(sys.modules, "cloakbrowser", cloakbrowser)
    monkeypatch.setattr(setup.importlib.metadata, "version", lambda name: "1.0.0")
    monkeypatch.setattr(
        setup,
        "get_config",
        lambda: {"runtime": {"cloakbrowser_cache_dir": "/tmp/cache"}, "extensions": {}},
    )
    monkeypatch.setattr(setup, "apply_environment", lambda cfg: None)
    monkeypatch.setattr(setup, "load_manifest", lambda: {})
    saved = []
    monkeypatch.setattr(
        setup, "save_manifest", lambda manifest: saved.append(dict(manifest)) or manifest
    )
    monkeypatch.setattr(setup, "install_system_dependencies", lambda noninteractive: {"ok": True})
    monkeypatch.setattr(setup, "install_python_dependencies", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(setup, "ensure_masquerade", lambda binary: tmp_path / "chrome")
    monkeypatch.setattr(
        setup, "ensure_display", lambda cfg, manifest: {"ok": True, "display": ":99"}
    )
    monkeypatch.setattr(setup, "install_configured_extensions", lambda cfg, manifest: [])
    monkeypatch.setattr(setup, "sync_browser_extension_paths", lambda cfg: [])
    monkeypatch.setattr(setup, "verify_extension_reconciliation", lambda cfg: {"ok": True})
    monkeypatch.setattr(
        setup,
        "patch_runtime_source",
        lambda manifest: {"applied": True, "already_patched": False},
    )
    monkeypatch.setattr(
        setup,
        "patch_ws_browser_source",
        lambda manifest: {"applied": True, "already_patched": False},
    )
    monkeypatch.setattr(
        setup,
        "patch_browser_store_source",
        lambda manifest: {"applied": True, "already_patched": False},
    )
    monkeypatch.setattr(setup, "validate_runtime_patch", lambda manifest: {"ok": True})
    monkeypatch.setattr(setup, "verify_browser_launch", lambda: {"ok": True})
    monkeypatch.setattr(
        setup,
        "reconcile_after_setup",
        lambda cfg, source_patch: {
            "browser_processes_stopped": {"matched": []},
            "agent_zero_restart": {"needed": True, "restarted": False, "reason": "not_found"},
            "restart_required": True,
        },
    )
    monkeypatch.setattr(setup, "managed_extension_paths", lambda: {})
    monkeypatch.setattr(setup, "disable_managed_extension_paths", lambda: [])
    monkeypatch.setattr(setup, "remove_masquerade", lambda path=None: True)
    monkeypatch.setattr(
        setup, "remove_supervisor_config_if_owned", lambda manifest: {"removed": ""}
    )
    monkeypatch.setattr(setup, "remove_direct_xvfb_if_owned", lambda manifest: {"removed": False})

    result = setup.setup_plugin(noninteractive=True)

    assert result["ok"] is False
    assert "Agent Zero restart required" in result["error"]
    assert saved[-1]["setup_status"] == "failed"
    assert saved[-1]["last_repair_status"] == "failed"


def test_setup_succeeds_when_agent_zero_restart_is_scheduled(monkeypatch, tmp_path):
    cloakbrowser = types.ModuleType("cloakbrowser")
    cloakbrowser.ensure_binary = lambda: "/bin/cloakbrowser"
    monkeypatch.setitem(sys.modules, "cloakbrowser", cloakbrowser)
    monkeypatch.setattr(setup.importlib.metadata, "version", lambda name: "1.0.0")
    monkeypatch.setattr(
        setup,
        "get_config",
        lambda: {"runtime": {"cloakbrowser_cache_dir": "/tmp/cache"}, "extensions": {}},
    )
    monkeypatch.setattr(setup, "apply_environment", lambda cfg: None)
    monkeypatch.setattr(setup, "load_manifest", lambda: {})
    saved = []
    monkeypatch.setattr(
        setup, "save_manifest", lambda manifest: saved.append(dict(manifest)) or manifest
    )
    monkeypatch.setattr(setup, "install_system_dependencies", lambda noninteractive: {"ok": True})
    monkeypatch.setattr(setup, "install_python_dependencies", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(setup, "ensure_masquerade", lambda binary: tmp_path / "chrome")
    monkeypatch.setattr(
        setup, "ensure_display", lambda cfg, manifest: {"ok": True, "display": ":99"}
    )
    monkeypatch.setattr(setup, "install_configured_extensions", lambda cfg, manifest: [])
    monkeypatch.setattr(setup, "sync_browser_extension_paths", lambda cfg: [])
    monkeypatch.setattr(setup, "verify_extension_reconciliation", lambda cfg: {"ok": True})
    monkeypatch.setattr(
        setup,
        "patch_runtime_source",
        lambda manifest: {"applied": True, "already_patched": False},
    )
    monkeypatch.setattr(
        setup,
        "patch_ws_browser_source",
        lambda manifest: {"applied": True, "already_patched": False},
    )
    monkeypatch.setattr(
        setup,
        "patch_browser_store_source",
        lambda manifest: {"applied": True, "already_patched": False},
    )
    monkeypatch.setattr(setup, "validate_runtime_patch", lambda manifest: {"ok": True})
    verify_calls = []
    monkeypatch.setattr(setup, "verify_browser_launch", lambda: verify_calls.append(True))
    monkeypatch.setattr(
        setup,
        "reconcile_after_setup",
        lambda cfg, source_patch: {
            "browser_processes_stopped": {"matched": []},
            "agent_zero_restart": {
                "needed": True,
                "scheduled": True,
                "message": "Agent Zero run_ui restart scheduled in 10 seconds.",
            },
            "restart_required": False,
        },
    )

    result = setup.setup_plugin(noninteractive=True)

    assert result["ok"] is True
    assert result["restart_scheduled"] is True
    assert result["launch_verification"]["skipped"] is True
    assert verify_calls == []
    assert saved[-1]["setup_status"] == "setup"


def test_setup_failure_rolls_back_plugin_owned_state(monkeypatch, tmp_path):
    cloakbrowser = types.ModuleType("cloakbrowser")
    cloakbrowser.ensure_binary = lambda: "/bin/cloakbrowser"
    monkeypatch.setitem(sys.modules, "cloakbrowser", cloakbrowser)
    monkeypatch.setattr(setup.importlib.metadata, "version", lambda name: "1.0.0")
    monkeypatch.setattr(
        setup,
        "get_config",
        lambda: {"runtime": {"cloakbrowser_cache_dir": "/tmp/cache"}, "extensions": {}},
    )
    monkeypatch.setattr(setup, "apply_environment", lambda cfg: None)
    monkeypatch.setattr(setup, "load_manifest", lambda: {})
    saved = []
    monkeypatch.setattr(
        setup, "save_manifest", lambda manifest: saved.append(dict(manifest)) or manifest
    )
    monkeypatch.setattr(setup, "install_system_dependencies", lambda noninteractive: {"ok": True})
    monkeypatch.setattr(setup, "install_python_dependencies", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(setup, "ensure_masquerade", lambda binary: tmp_path / "chrome")
    monkeypatch.setattr(
        setup, "ensure_display", lambda cfg, manifest: {"ok": True, "display": ":99"}
    )
    monkeypatch.setattr(
        setup,
        "install_configured_extensions",
        lambda cfg, manifest: (_ for _ in ()).throw(RuntimeError("extension failed")),
    )
    incomplete = tmp_path / "incomplete-extension"
    incomplete.mkdir()
    monkeypatch.setattr(setup, "managed_extension_paths", lambda: {"broken": incomplete})
    monkeypatch.setattr(setup, "disable_managed_extension_paths", lambda: ["/managed"])
    monkeypatch.setattr(setup, "remove_masquerade", lambda path=None: True)
    monkeypatch.setattr(
        setup, "remove_supervisor_config_if_owned", lambda manifest: {"removed": ""}
    )
    monkeypatch.setattr(setup, "remove_direct_xvfb_if_owned", lambda manifest: {"removed": False})

    result = setup.setup_plugin(noninteractive=True)

    assert result["ok"] is False
    assert result["rollback"]["disabled_extension_paths"] == ["/managed"]
    assert result["rollback"]["shared_dependencies_removed"] is False
    assert result["rollback"]["preserved_prior_setup"] is False
    assert not incomplete.exists()
    assert saved[-1]["setup_status"] == "failed"


def test_python_dependency_failure_preserves_existing_runtime_state(monkeypatch):
    rollback_calls = []
    saved = []
    monkeypatch.setattr(setup, "get_config", lambda: {"runtime": {}, "extensions": {}})
    monkeypatch.setattr(setup, "apply_environment", lambda cfg: None)
    monkeypatch.setattr(setup, "load_manifest", lambda: {"setup_status": "setup"})
    monkeypatch.setattr(
        setup, "save_manifest", lambda manifest: saved.append(dict(manifest)) or manifest
    )
    monkeypatch.setattr(setup, "install_system_dependencies", lambda noninteractive: {"ok": True})
    monkeypatch.setattr(setup, "install_python_dependencies", lambda **kwargs: {"ok": False})
    monkeypatch.setattr(
        setup, "_rollback_failed_setup", lambda manifest: rollback_calls.append(manifest)
    )

    result = setup.setup_plugin(noninteractive=True)

    assert result["ok"] is False
    assert rollback_calls == []
    assert saved[-1]["setup_status"] == "setup"
    assert saved[-1]["last_repair_status"] == "failed"


def test_late_setup_failure_preserves_previous_successful_state(monkeypatch, tmp_path):
    cloakbrowser = types.ModuleType("cloakbrowser")
    cloakbrowser.ensure_binary = lambda: "/bin/cloakbrowser"
    monkeypatch.setitem(sys.modules, "cloakbrowser", cloakbrowser)
    monkeypatch.setattr(setup.importlib.metadata, "version", lambda name: "1.0.0")
    monkeypatch.setattr(
        setup,
        "get_config",
        lambda: {"runtime": {"cloakbrowser_cache_dir": "/tmp/cache"}, "extensions": {}},
    )
    monkeypatch.setattr(setup, "apply_environment", lambda cfg: None)
    monkeypatch.setattr(
        setup,
        "load_manifest",
        lambda: {
            "setup_status": "setup",
            "playwright_shim": {"masquerade_path": "/previous/chrome"},
            "xvfb": {"managed_by": "cloakbrowser", "pid": 123, "display": ":99"},
        },
    )
    saved = []
    monkeypatch.setattr(
        setup, "save_manifest", lambda manifest: saved.append(dict(manifest)) or manifest
    )
    monkeypatch.setattr(setup, "install_system_dependencies", lambda noninteractive: {"ok": True})
    monkeypatch.setattr(setup, "install_python_dependencies", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(setup, "ensure_masquerade", lambda binary: tmp_path / "chrome")
    monkeypatch.setattr(
        setup, "ensure_display", lambda cfg, manifest: {"ok": True, "display": ":99"}
    )
    monkeypatch.setattr(
        setup,
        "install_configured_extensions",
        lambda cfg, manifest: (_ for _ in ()).throw(RuntimeError("extension failed")),
    )
    incomplete = tmp_path / "incomplete-extension"
    incomplete.mkdir()
    monkeypatch.setattr(setup, "managed_extension_paths", lambda: {"broken": incomplete})
    rollback_calls = {"disable": 0, "masquerade": 0, "supervisor": 0, "xvfb": 0}
    monkeypatch.setattr(
        setup, "disable_managed_extension_paths", lambda: rollback_calls.__setitem__("disable", 1)
    )
    monkeypatch.setattr(
        setup, "remove_masquerade", lambda path=None: rollback_calls.__setitem__("masquerade", 1)
    )
    monkeypatch.setattr(
        setup,
        "remove_supervisor_config_if_owned",
        lambda manifest: rollback_calls.__setitem__("supervisor", 1),
    )
    monkeypatch.setattr(
        setup, "remove_direct_xvfb_if_owned", lambda manifest: rollback_calls.__setitem__("xvfb", 1)
    )

    result = setup.setup_plugin(noninteractive=True)

    assert result["ok"] is False
    assert result["rollback"]["preserved_prior_setup"] is True
    assert rollback_calls == {"disable": 0, "masquerade": 0, "supervisor": 0, "xvfb": 0}
    assert incomplete.exists()
    assert saved[-1]["setup_status"] == "setup"
    assert saved[-1]["last_repair_status"] == "failed"
