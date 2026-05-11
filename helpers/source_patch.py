from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .patcher import backup_file, sha256_file

PATCH_VERSION = "1"
PATCH_MARKER = "CLOAKBROWSER_SOURCE_PATCH_V1"

SOURCE_RUNTIME_HELPER = f"""

# {PATCH_MARKER}: start
def _cloakbrowser_source_runtime():
    try:
        from helpers import plugins as _cloakbrowser_plugins

        _cloakbrowser_dir = _cloakbrowser_plugins.find_plugin_dir("cloakbrowser")
        if _cloakbrowser_dir:
            import sys as _cloakbrowser_sys

            if _cloakbrowser_dir not in _cloakbrowser_sys.path:
                _cloakbrowser_sys.path.insert(0, _cloakbrowser_dir)
        from plugin_imports import plugin_import as _cloakbrowser_plugin_import

        return _cloakbrowser_plugin_import("helpers.source_runtime")
    except Exception as exc:
        try:
            PrintStyle.warning(f"CloakBrowser source patch unavailable: {{exc}}")
        except Exception:
            pass
        return None
# {PATCH_MARKER}: end
"""

LAUNCH_ORIGINAL = """        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                **launch_kwargs
            )
"""

LAUNCH_PATCHED = """        _cloakbrowser_runtime = _cloakbrowser_source_runtime()
        try:
            if _cloakbrowser_runtime:
                self.context = await _cloakbrowser_runtime.launch_persistent_context(
                    self.playwright.chromium,
                    launch_kwargs,
                )
            else:
                self.context = await self.playwright.chromium.launch_persistent_context(
                    **launch_kwargs
                )
"""

SHADOW_ORIGINAL = """        await self.context.add_init_script(self._shadow_dom_script())
"""

SHADOW_PATCHED = """        if not (_cloakbrowser_runtime and _cloakbrowser_runtime.disable_shadow_dom_init()):
            await self.context.add_init_script(self._shadow_dom_script())
"""

START_PAGES_ORIGINAL = """        for page in list(self.context.pages):
            if page.url == "about:blank":
                try:
                    await page.close()
                except Exception:
                    pass
                continue
            await self._register_page(page)
"""

START_PAGES_PATCHED = """        for page in list(self.context.pages):
            if page.url == "about:blank":
                if len(self.context.pages) == 1:
                    continue
                try:
                    await page.close()
                except Exception:
                    pass
                continue
            await self._register_page(page)
"""

OPEN_ORIGINAL = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

OPEN_PATCHED = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        page = None
        if not self.pages:
            for candidate in list(self.context.pages):
                if candidate.url == "about:blank":
                    page = candidate
                    break
        if page is None:
            try:
                page = await self.context.new_page()
            except Exception:
                if self.pages:
                    raise
                await self._discard_stale_context("Browser context could not open a new tab; restarting.")
                await self.ensure_started()
                for candidate in list(self.context.pages):
                    if candidate.url == "about:blank":
                        page = candidate
                        break
                if page is None:
                    page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

def patch_runtime_source(manifest: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    if not config["advanced"]["patch_runtime_file_if_needed"]:
        result = {"applied": False, "reason": "disabled"}
        manifest["runtime_source_patch"] = result
        return result

    target = browser_runtime_source_path()
    original_text = target.read_text(encoding="utf-8")
    if PATCH_MARKER in original_text:
        previous = manifest.get("runtime_source_patch") or {}
        result = {
            "applied": True,
            "already_patched": True,
            "target_path": str(target),
            "backup_path": previous.get("backup_path", ""),
            "original_hash": previous.get("original_hash", ""),
            "patched_hash": sha256_file(target),
            "patch_version": PATCH_VERSION,
        }
        manifest["runtime_source_patch"] = result
        _record_runtime_patch(manifest, result)
        return result

    original_hash = sha256_file(target)
    patched_text = patch_runtime_source_text(original_text)
    backup = backup_file(target, target.parent / ".cloakbrowser-backups")
    target.write_text(patched_text, encoding="utf-8")
    patched_hash = sha256_file(target)
    result = {
        "applied": True,
        "already_patched": False,
        "target_path": str(target),
        "backup_path": str(backup),
        "original_hash": original_hash,
        "patched_hash": patched_hash,
        "patch_version": PATCH_VERSION,
    }
    manifest["runtime_source_patch"] = result
    _record_runtime_patch(manifest, result)
    return result


def restore_runtime_source_patch(manifest: dict[str, Any]) -> dict[str, Any]:
    patch = manifest.get("runtime_source_patch") or {}
    target_path = patch.get("target_path")
    backup_path = patch.get("backup_path")
    patched_hash = patch.get("patched_hash")
    if not target_path or not backup_path or not patched_hash:
        return {"restored": False, "reason": "not_patched"}

    target = Path(str(target_path))
    backup = Path(str(backup_path))
    if not target.is_file() or not backup.is_file():
        return {"restored": False, "reason": "missing_file", "target_path": str(target)}
    current_hash = sha256_file(target)
    if current_hash != patched_hash:
        return {
            "restored": False,
            "reason": "current_hash_mismatch",
            "target_path": str(target),
            "current_hash": current_hash,
            "expected_hash": patched_hash,
        }
    shutil.copy2(backup, target)
    return {"restored": True, "target_path": str(target), "restored_hash": sha256_file(target)}


def browser_runtime_source_path() -> Path:
    from .runtime_patch import _agent_zero_import_context

    with _agent_zero_import_context():
        from plugins._browser.helpers import runtime

        return Path(runtime.__file__).resolve()


def patch_runtime_source_text(text: str) -> str:
    patched = text
    if SOURCE_RUNTIME_HELPER.strip() not in patched:
        anchor = 'CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"\n'
        patched = _replace_once(patched, anchor, anchor + SOURCE_RUNTIME_HELPER)
    patched = _replace_once(patched, LAUNCH_ORIGINAL, LAUNCH_PATCHED)
    patched = _replace_once(patched, SHADOW_ORIGINAL, SHADOW_PATCHED)
    patched = _replace_once(patched, START_PAGES_ORIGINAL, START_PAGES_PATCHED)
    patched = _replace_once(patched, OPEN_ORIGINAL, OPEN_PATCHED)
    return patched


def _replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected one runtime source patch target, found {count}")
    return text.replace(old, new, 1)


def _record_runtime_patch(manifest: dict[str, Any], result: dict[str, Any]) -> None:
    patches = [
        patch
        for patch in manifest.get("runtime_patches", [])
        if patch.get("kind") != "source_runtime"
    ]
    patches.append({"kind": "source_runtime", **result})
    manifest["runtime_patches"] = patches
