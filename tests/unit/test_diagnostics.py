from helpers import diagnostics


def test_status_separates_setup_from_process_local_patches(monkeypatch):
    monkeypatch.setattr(
        diagnostics,
        "load_manifest",
        lambda: {
            "setup_status": "setup",
            "setup_timestamp": "2026-05-09T00:00:00Z",
            "playwright_shim": {"masquerade_path": "/tmp/chrome"},
        },
    )
    monkeypatch.setattr(diagnostics, "display_usable", lambda display: False)
    monkeypatch.setattr(diagnostics, "cloakbrowser_status", lambda: {"installed": True})
    monkeypatch.setattr(diagnostics, "browser_status", lambda: {"upstream_available": True})
    monkeypatch.setattr(diagnostics, "active_extension_paths", lambda cfg: [])
    monkeypatch.setattr(diagnostics, "list_extension_status", lambda cfg: [])
    monkeypatch.setattr(
        diagnostics,
        "shim_status",
        lambda: {"patched": False, "patching": "process-local", "persistent": False},
    )
    monkeypatch.setattr(
        diagnostics,
        "runtime_patch_status",
        lambda: {"patched": False, "patching": "process-local", "persistent": False},
    )

    status = diagnostics.collect_status()

    assert status["setup"]["installed"] is True
    assert status["environment"]["shared_memory"]["available"] is True
    assert status["patches"]["playwright_shim"]["setup_installed"] is True
    assert status["patches"]["playwright_shim"]["patched"] is False
    assert status["patches"]["runtime_patch"]["setup_installed"] is False
    assert status["patches"]["arg_filtering"] == "always_on"


def test_shared_memory_status_reports_missing_path():
    status = diagnostics.shared_memory_status("/path/that/does/not/exist")

    assert status["available"] is False
    assert status["path"] == "/path/that/does/not/exist"
