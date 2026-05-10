import json

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

    assert execute.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["command"] == "run"
