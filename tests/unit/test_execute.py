import json
import sys
import types

import execute
import plugin_imports


def _status():
    return {
        "setup": {"installed": True, "status": "setup"},
        "config": {"runtime": {"headed": True, "cloakbrowser_cache_dir": "/opt/cloakbrowser"}},
        "cloakbrowser": {"installed": True, "version": "1.2.3", "binary_path": "/bin/chrome"},
        "display": {"current": ":99", "configured": ":99", "usable_current": True, "usable_configured": True},
        "browser": {"upstream_available": True},
        "extensions": {"active_paths": ["/ext/ubol"], "items": []},
    }


def test_ensure_agent_zero_path_uses_git_fallback_for_legacy_plugin_root(monkeypatch, tmp_path):
    root = tmp_path / "a0" / "usr" / "plugins" / "cloakbrowser"
    root.mkdir(parents=True)
    fallback = tmp_path / "git" / "agent-zero"
    (fallback / "plugins" / "_browser").mkdir(parents=True)
    (fallback / "helpers").mkdir()
    (fallback / "helpers" / "tool.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(plugin_imports, "AGENT_ZERO_FALLBACK_DIR", fallback)
    monkeypatch.setattr(sys, "path", [str(root)])

    plugin_imports.ensure_agent_zero_path(root)

    assert sys.path[0] == str(fallback)


def test_no_arg_execute_runs_setup_then_status_human_readable(monkeypatch, capsys):
    calls = []

    def fake_import(name):
        if name == "helpers.setup":
            return type(
                "Setup",
                (),
                {
                    "setup_plugin": lambda **kwargs: calls.append(kwargs)
                    or {
                        "ok": True,
                        "system": {"ok": True, "installed_packages": ["xvfb"], "failed_packages": []},
                        "python": {"ok": True, "command": ["python", "-m", "pip", "install"]},
                        "display": {"ok": True, "display": ":99", "reused": True},
                        "extension_actions": [
                            {
                                "name": "uBlock Origin Lite",
                                "action": "reused",
                                "installed": True,
                                "enabled": True,
                            }
                        ],
                    },
                },
            )
        if name == "helpers.diagnostics":
            return type("Diagnostics", (), {"collect_status": _status})
        raise AssertionError(name)

    monkeypatch.setattr(plugin_imports, "plugin_import", fake_import)
    monkeypatch.setattr(execute, "_is_plugin_enabled", lambda: True)

    assert execute.main([]) == 0
    output = capsys.readouterr().out

    assert calls == [{"noninteractive": True, "skip_system_deps": False}]
    assert "CloakBrowser setup" in output
    assert "Final readiness: ready" in output
    assert not output.lstrip().startswith("{")


def test_execute_json_mode_is_machine_readable(monkeypatch, capsys):
    def fake_import(name):
        if name == "helpers.setup":
            return type(
                "Setup",
                (),
                {"setup_plugin": lambda **kwargs: {"ok": True, "system": {}, "python": {}}},
            )
        if name == "helpers.diagnostics":
            return type("Diagnostics", (), {"collect_status": _status})
        raise AssertionError(name)

    monkeypatch.setattr(plugin_imports, "plugin_import", fake_import)
    monkeypatch.setattr(execute, "_is_plugin_enabled", lambda: True)

    assert execute.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["command"] == "run"


def test_execute_run_uninstalls_when_plugin_disabled(monkeypatch, capsys):
    calls = []

    def fake_import(name):
        if name == "helpers.uninstall":
            return type(
                "Uninstall",
                (),
                {
                    "uninstall": lambda **kwargs: calls.append(kwargs)
                    or {
                        "ok": True,
                        "disabled_extension_paths": ["/git/agent-zero/usr/plugins/cloakbrowser/.cloakbrowser/extensions/ubol"],
                        "masquerade_removed": True,
                        "restart_required": False,
                    },
                },
            )
        raise AssertionError(name)

    monkeypatch.setattr(plugin_imports, "plugin_import", fake_import)
    monkeypatch.setattr(execute, "_is_plugin_enabled", lambda: False)

    assert execute.main([]) == 0

    assert calls == [{"remove_extensions": False}]
    assert "CloakBrowser uninstall" in capsys.readouterr().out


def test_execute_run_force_sets_up_even_when_plugin_disabled(monkeypatch, capsys):
    calls = []

    def fake_import(name):
        if name == "helpers.setup":
            return type(
                "Setup",
                (),
                {"setup_plugin": lambda **kwargs: calls.append(kwargs) or {"ok": True}},
            )
        if name == "helpers.diagnostics":
            return type("Diagnostics", (), {"collect_status": _status})
        raise AssertionError(name)

    monkeypatch.setattr(plugin_imports, "plugin_import", fake_import)
    monkeypatch.setattr(execute, "_is_plugin_enabled", lambda: False)

    assert execute.main(["--force", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert calls == [{"noninteractive": True, "skip_system_deps": False}]
    assert payload["command"] == "run"


def test_plugin_enabled_check_uses_agent_zero_helpers_not_local_helpers(monkeypatch, tmp_path):
    agent_zero = tmp_path / "agent-zero"
    helpers_dir = agent_zero / "helpers"
    helpers_dir.mkdir(parents=True)
    (helpers_dir / "__init__.py").write_text("", encoding="utf-8")
    (helpers_dir / "plugins.py").write_text(
        "def get_enabled_plugins(_scope):\n    return ['_browser']\n",
        encoding="utf-8",
    )
    local_helpers = types.ModuleType("helpers")
    local_helpers.__file__ = str(execute.Path(__file__).resolve().parents[2] / "helpers" / "__init__.py")
    monkeypatch.setitem(sys.modules, "helpers", local_helpers)
    monkeypatch.syspath_prepend(str(agent_zero))
    monkeypatch.setattr(plugin_imports, "ensure_agent_zero_path", lambda _root: None)

    assert execute._is_plugin_enabled() is False
