import sys
import types

from helpers import setup


def test_setup_failure_rolls_back_plugin_owned_state(monkeypatch, tmp_path):
    cloakbrowser = types.ModuleType("cloakbrowser")
    cloakbrowser.ensure_binary = lambda: "/bin/cloakbrowser"
    monkeypatch.setitem(sys.modules, "cloakbrowser", cloakbrowser)
    monkeypatch.setattr(setup.importlib.metadata, "version", lambda name: "1.0.0")
    monkeypatch.setattr(setup, "get_config", lambda: {"runtime": {"cloakbrowser_cache_dir": "/tmp/cache"}, "extensions": {}})
    monkeypatch.setattr(setup, "apply_environment", lambda cfg: None)
    monkeypatch.setattr(setup, "load_manifest", lambda: {})
    saved = []
    monkeypatch.setattr(setup, "save_manifest", lambda manifest: saved.append(dict(manifest)) or manifest)
    monkeypatch.setattr(setup, "install_system_dependencies", lambda noninteractive: {"ok": True})
    monkeypatch.setattr(setup, "install_python_dependencies", lambda: {"ok": True})
    monkeypatch.setattr(setup, "ensure_masquerade", lambda binary: tmp_path / "chrome")
    monkeypatch.setattr(setup, "ensure_display", lambda cfg, manifest: {"ok": True, "display": ":99"})
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
    monkeypatch.setattr(setup, "remove_supervisor_config_if_owned", lambda manifest: {"removed": ""})
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
    monkeypatch.setattr(setup, "save_manifest", lambda manifest: saved.append(dict(manifest)) or manifest)
    monkeypatch.setattr(setup, "install_system_dependencies", lambda noninteractive: {"ok": True})
    monkeypatch.setattr(setup, "install_python_dependencies", lambda: {"ok": False})
    monkeypatch.setattr(setup, "_rollback_failed_setup", lambda manifest: rollback_calls.append(manifest))

    result = setup.setup_plugin(noninteractive=True)

    assert result["ok"] is False
    assert rollback_calls == []
    assert saved[-1]["setup_status"] == "failed"


def test_late_setup_failure_preserves_previous_successful_state(monkeypatch, tmp_path):
    cloakbrowser = types.ModuleType("cloakbrowser")
    cloakbrowser.ensure_binary = lambda: "/bin/cloakbrowser"
    monkeypatch.setitem(sys.modules, "cloakbrowser", cloakbrowser)
    monkeypatch.setattr(setup.importlib.metadata, "version", lambda name: "1.0.0")
    monkeypatch.setattr(setup, "get_config", lambda: {"runtime": {"cloakbrowser_cache_dir": "/tmp/cache"}, "extensions": {}})
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
    monkeypatch.setattr(setup, "save_manifest", lambda manifest: saved.append(dict(manifest)) or manifest)
    monkeypatch.setattr(setup, "install_system_dependencies", lambda noninteractive: {"ok": True})
    monkeypatch.setattr(setup, "install_python_dependencies", lambda: {"ok": True})
    monkeypatch.setattr(setup, "ensure_masquerade", lambda binary: tmp_path / "chrome")
    monkeypatch.setattr(setup, "ensure_display", lambda cfg, manifest: {"ok": True, "display": ":99"})
    monkeypatch.setattr(
        setup,
        "install_configured_extensions",
        lambda cfg, manifest: (_ for _ in ()).throw(RuntimeError("extension failed")),
    )
    incomplete = tmp_path / "incomplete-extension"
    incomplete.mkdir()
    monkeypatch.setattr(setup, "managed_extension_paths", lambda: {"broken": incomplete})
    rollback_calls = {"disable": 0, "masquerade": 0, "supervisor": 0, "xvfb": 0}
    monkeypatch.setattr(setup, "disable_managed_extension_paths", lambda: rollback_calls.__setitem__("disable", 1))
    monkeypatch.setattr(setup, "remove_masquerade", lambda path=None: rollback_calls.__setitem__("masquerade", 1))
    monkeypatch.setattr(setup, "remove_supervisor_config_if_owned", lambda manifest: rollback_calls.__setitem__("supervisor", 1))
    monkeypatch.setattr(setup, "remove_direct_xvfb_if_owned", lambda manifest: rollback_calls.__setitem__("xvfb", 1))

    result = setup.setup_plugin(noninteractive=True)

    assert result["ok"] is False
    assert result["rollback"]["preserved_prior_setup"] is True
    assert rollback_calls == {"disable": 0, "masquerade": 0, "supervisor": 0, "xvfb": 0}
    assert incomplete.exists()
    assert saved[-1]["setup_status"] == "failed"
