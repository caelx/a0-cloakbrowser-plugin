from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .patcher import backup_file, sha256_file

PATCH_VERSION = "7"
PATCH_MARKER = "CLOAKBROWSER_SOURCE_PATCH_V7"
OLD_PATCH_MARKERS = (
    "CLOAKBROWSER_SOURCE_PATCH_V1",
    "CLOAKBROWSER_SOURCE_PATCH_V2",
    "CLOAKBROWSER_SOURCE_PATCH_V3",
    "CLOAKBROWSER_SOURCE_PATCH_V4",
    "CLOAKBROWSER_SOURCE_PATCH_V5",
    "CLOAKBROWSER_SOURCE_PATCH_V6",
)

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
            if page.url == "about:blank" and len(self.context.pages) == 1:
                continue
            if page.url == "about:blank":
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
            for candidate in list(getattr(self.context, "pages", [])):
                if not getattr(candidate, "is_closed", lambda: False)():
                    page = candidate
                    break
        if page is None:
            try:
                page = await self.context.new_page()
            except Exception:
                if self.pages:
                    raise
                lock = getattr(self, "_cloakbrowser_open_restart_lock", None)
                if lock is None:
                    lock = asyncio.Lock()
                    self._cloakbrowser_open_restart_lock = lock
                async with lock:
                    await self.ensure_started()
                    if not self.pages:
                        for candidate in list(getattr(self.context, "pages", [])):
                            if not getattr(candidate, "is_closed", lambda: False)():
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
                            for candidate in list(getattr(self.context, "pages", [])):
                                if not getattr(candidate, "is_closed", lambda: False)():
                                    page = candidate
                                    break
                            if page is None:
                                page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

START_PAGES_PATCHED_V1 = """        for page in list(self.context.pages):
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

OPEN_PATCHED_V1 = """    async def open(self, url: str = "") -> dict[str, Any]:
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

OPEN_PATCHED_V2 = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        try:
            page = await self.context.new_page()
        except Exception:
            if self.pages:
                raise
            lock = getattr(self, "_cloakbrowser_open_restart_lock", None)
            if lock is None:
                lock = asyncio.Lock()
                self._cloakbrowser_open_restart_lock = lock
            async with lock:
                await self.ensure_started()
                try:
                    page = await self.context.new_page()
                except Exception:
                    if self.pages:
                        raise
                    await self._discard_stale_context("Browser context could not open a new tab; restarting.")
                    await self.ensure_started()
                    page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

CLOSE_BROWSER_ORIGINAL = """    async def close_browser(self, browser_id: int | str | None = None) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        await self._stop_screencasts_for_browser(resolved_id)
        page = self._page(resolved_id)
        await page.close()
        self.pages.pop(resolved_id, None)
        if self.last_interacted_browser_id == resolved_id:
            self.last_interacted_browser_id = next(iter(sorted(self.pages)), None)
        return await self.list()
"""

CLOSE_BROWSER_PATCHED = """    async def close_browser(self, browser_id: int | str | None = None) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        await self._stop_screencasts_for_browser(resolved_id)
        page = self._page(resolved_id)
        expecting_context_close = len(self.pages) <= 1
        context_closed_future = None
        if expecting_context_close:
            context_closed_future = asyncio.get_running_loop().create_future()
            self._cloakbrowser_expected_context_close = True
            self._cloakbrowser_expected_context_close_future = context_closed_future
        try:
            await page.close()
        finally:
            if expecting_context_close and context_closed_future:
                try:
                    await asyncio.wait_for(asyncio.shield(context_closed_future), timeout=1)
                except asyncio.TimeoutError:
                    pass
                finally:
                    self._cloakbrowser_expected_context_close = False
                    self._cloakbrowser_expected_context_close_future = None
        self.pages.pop(resolved_id, None)
        if self.last_interacted_browser_id == resolved_id:
            self.last_interacted_browser_id = next(iter(sorted(self.pages)), None)
        if self.context is None and self.playwright:
            await self._stop_playwright("Playwright stop after CloakBrowser context loss failed")
        return await self.list()
"""

CLOSE_ALL_ORIGINAL = """    async def close_all_browsers(self) -> dict[str, Any]:
        await self.ensure_started()
        await self._stop_all_screencasts()
        for browser_id in list(self.pages):
            try:
                await self.pages[browser_id].page.close()
            except Exception:
                pass
        self.pages.clear()
        self.last_interacted_browser_id = None
        return {"browsers": [], "last_interacted_browser_id": None}
"""

CLOSE_ALL_PATCHED = """    async def close_all_browsers(self) -> dict[str, Any]:
        await self.ensure_started()
        await self._stop_all_screencasts()
        expecting_context_close = bool(self.pages)
        context_closed_future = None
        if expecting_context_close:
            context_closed_future = asyncio.get_running_loop().create_future()
            self._cloakbrowser_expected_context_close = True
            self._cloakbrowser_expected_context_close_future = context_closed_future
        try:
            for browser_id in list(self.pages):
                try:
                    await self.pages[browser_id].page.close()
                except Exception:
                    pass
        finally:
            if expecting_context_close and context_closed_future:
                try:
                    await asyncio.wait_for(asyncio.shield(context_closed_future), timeout=1)
                except asyncio.TimeoutError:
                    pass
                finally:
                    self._cloakbrowser_expected_context_close = False
                    self._cloakbrowser_expected_context_close_future = None
        self.pages.clear()
        self.last_interacted_browser_id = None
        if self.context is None and self.playwright:
            await self._stop_playwright("Playwright stop after CloakBrowser context loss failed")
        return {"browsers": [], "last_interacted_browser_id": None}
"""

CONTEXT_CLOSED_ORIGINAL = """    def _on_context_closed(self) -> None:
        if self._closing or self.context is None:
            return
        PrintStyle.warning("Browser context closed unexpectedly; will restart on next use.")
        self._discard_context_state()
"""

CONTEXT_CLOSED_PATCHED = """    def _on_context_closed(self) -> None:
        if self._closing or self.context is None:
            return
        if getattr(self, "_cloakbrowser_expected_context_close", False):
            future = getattr(self, "_cloakbrowser_expected_context_close_future", None)
            self._discard_context_state()
            if future and not future.done():
                future.set_result(None)
            return
        PrintStyle.warning("Browser context closed unexpectedly; will restart on next use.")
        self._discard_context_state()
"""

STOP_PLAYWRIGHT_ORIGINAL = """    async def _stop_playwright(self, warning: str) -> None:
        if not self.playwright:
            return
        try:
            await self.playwright.stop()
        except Exception as exc:
            PrintStyle.warning(f"{warning}: {exc}")
        finally:
            self.playwright = None
"""

STOP_PLAYWRIGHT_PATCHED = """    async def _stop_playwright(self, warning: str) -> None:
        if not self.playwright:
            return
        playwright = self.playwright
        self.playwright = None
        try:
            await playwright.stop()
        except Exception as exc:
            PrintStyle.warning(f"{warning}: {exc}")
        finally:
            import gc

            gc.collect()
            await asyncio.sleep(0.25)
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
    is_old_patch = any(marker in original_text for marker in OLD_PATCH_MARKERS)

    original_hash = sha256_file(target)
    patched_text = (
        upgrade_runtime_source_text(original_text) if is_old_patch else patch_runtime_source_text(original_text)
    )
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
        "upgraded": is_old_patch,
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
    patched = _replace_once(patched, CLOSE_BROWSER_ORIGINAL, CLOSE_BROWSER_PATCHED)
    patched = _replace_once(patched, CLOSE_ALL_ORIGINAL, CLOSE_ALL_PATCHED)
    patched = _replace_once(patched, CONTEXT_CLOSED_ORIGINAL, CONTEXT_CLOSED_PATCHED)
    patched = _replace_once(patched, STOP_PLAYWRIGHT_ORIGINAL, STOP_PLAYWRIGHT_PATCHED)
    return patched


def upgrade_runtime_source_text(text: str) -> str:
    patched = text
    for old_marker in OLD_PATCH_MARKERS:
        patched = patched.replace(old_marker, PATCH_MARKER)
    if START_PAGES_PATCHED in patched:
        pass
    elif START_PAGES_PATCHED_V1 in patched:
        patched = _replace_once(patched, START_PAGES_PATCHED_V1, START_PAGES_PATCHED)
    else:
        patched = _replace_once(patched, START_PAGES_ORIGINAL, START_PAGES_PATCHED)
    patched = _replace_first_matching_once(
        patched,
        (OPEN_PATCHED, OPEN_PATCHED_V2, OPEN_PATCHED_V1, OPEN_ORIGINAL),
        OPEN_PATCHED,
    )
    patched = _replace_first_matching_once(
        patched,
        (CLOSE_BROWSER_PATCHED, CLOSE_BROWSER_ORIGINAL),
        CLOSE_BROWSER_PATCHED,
    )
    patched = _replace_first_matching_once(
        patched,
        (CLOSE_ALL_PATCHED, CLOSE_ALL_ORIGINAL),
        CLOSE_ALL_PATCHED,
    )
    patched = _replace_first_matching_once(
        patched,
        (CONTEXT_CLOSED_PATCHED, CONTEXT_CLOSED_ORIGINAL),
        CONTEXT_CLOSED_PATCHED,
    )
    patched = _replace_first_matching_once(
        patched,
        (STOP_PLAYWRIGHT_PATCHED, STOP_PLAYWRIGHT_ORIGINAL),
        STOP_PLAYWRIGHT_PATCHED,
    )
    if PATCH_MARKER not in patched:
        raise ValueError("Expected upgraded runtime source to contain current patch marker")
    return patched


def _replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected one runtime source patch target, found {count}")
    return text.replace(old, new, 1)


def _replace_first_matching_once(text: str, candidates: tuple[str, ...], new: str) -> str:
    for old in candidates:
        if old in text:
            return _replace_once(text, old, new)
    raise ValueError("Expected one runtime source patch target, found 0")


def _record_runtime_patch(manifest: dict[str, Any], result: dict[str, Any]) -> None:
    patches = [
        patch
        for patch in manifest.get("runtime_patches", [])
        if patch.get("kind") != "source_runtime"
    ]
    patches.append({"kind": "source_runtime", **result})
    manifest["runtime_patches"] = patches
