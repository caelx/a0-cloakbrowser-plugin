from helpers import source_patch, validation


def test_validate_runtime_patch_accepts_complete_current_patch(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    ws_browser = tmp_path / "ws_browser.py"
    runtime.write_text(source_patch.patch_runtime_source_text(_runtime_source()), encoding="utf-8")
    ws_browser.write_text(source_patch.patch_ws_browser_source_text(_ws_browser_source()), encoding="utf-8")
    backup = tmp_path / "runtime.backup.py"
    ws_backup = tmp_path / "ws_browser.backup.py"
    backup.write_text(_runtime_source(), encoding="utf-8")
    ws_backup.write_text(_ws_browser_source(), encoding="utf-8")
    manifest = {
        "runtime_source_patch": {
            "target_path": str(runtime),
            "backup_path": str(backup),
            "original_hash": source_patch.sha256_file(backup),
            "patched_hash": source_patch.sha256_file(runtime),
            "patch_version": source_patch.PATCH_VERSION,
        },
        "ws_browser_source_patch": {
            "target_path": str(ws_browser),
            "backup_path": str(ws_backup),
            "original_hash": source_patch.sha256_file(ws_backup),
            "patched_hash": source_patch.sha256_file(ws_browser),
            "patch_version": source_patch.WS_PATCH_VERSION,
        },
    }
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    monkeypatch.setattr(source_patch, "browser_ws_source_path", lambda: ws_browser)

    result = validation.validate_runtime_patch(manifest)

    assert result["ok"] is True
    assert result["failed"] == []


def test_validate_runtime_patch_reports_missing_launch_patch(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    ws_browser = tmp_path / "ws_browser.py"
    runtime.write_text(source_patch.SOURCE_RUNTIME_HELPER, encoding="utf-8")
    ws_browser.write_text(source_patch.patch_ws_browser_source_text(_ws_browser_source()), encoding="utf-8")
    backup = tmp_path / "runtime.backup.py"
    ws_backup = tmp_path / "ws_browser.backup.py"
    backup.write_text(_runtime_source(), encoding="utf-8")
    ws_backup.write_text(_ws_browser_source(), encoding="utf-8")
    manifest = {
        "runtime_source_patch": {
            "target_path": str(runtime),
            "backup_path": str(backup),
            "original_hash": source_patch.sha256_file(backup),
            "patched_hash": source_patch.sha256_file(runtime),
            "patch_version": source_patch.PATCH_VERSION,
        },
        "ws_browser_source_patch": {
            "target_path": str(ws_browser),
            "backup_path": str(ws_backup),
            "original_hash": source_patch.sha256_file(ws_backup),
            "patched_hash": source_patch.sha256_file(ws_browser),
            "patch_version": source_patch.WS_PATCH_VERSION,
        },
    }
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    monkeypatch.setattr(source_patch, "browser_ws_source_path", lambda: ws_browser)

    result = validation.validate_runtime_patch(manifest)

    assert result["ok"] is False
    assert "launch_patch_present" in result["failed"]


def _runtime_source() -> str:
    return "\n".join(
        [
            'CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"',
            source_patch.LAUNCH_ORIGINAL,
            source_patch.CONTENT_HELPER_ORIGINAL,
            source_patch.START_PAGES_ORIGINAL,
            source_patch.OPEN_ORIGINAL,
            source_patch.CLOSE_BROWSER_ORIGINAL,
            source_patch.CLOSE_ALL_ORIGINAL,
            source_patch.CONTEXT_CLOSED_ORIGINAL,
            source_patch.STOP_PLAYWRIGHT_ORIGINAL,
        ]
    )


def _ws_browser_source() -> str:
    return "\n".join(
        [
            source_patch.WS_CLASS_ORIGINAL,
            "    async def _input(self, data, sid):",
            source_patch.WS_INPUT_ORIGINAL,
            "            result = {}",
            "        except Exception:",
            "            raise",
            "        return result",
        ]
    )
