from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .patcher import backup_file, sha256_file

PATCH_VERSION = "9"
PATCH_MARKER = "CLOAKBROWSER_SOURCE_PATCH_V9"
OLD_PATCH_MARKERS = (
    "CLOAKBROWSER_SOURCE_PATCH_V1",
    "CLOAKBROWSER_SOURCE_PATCH_V2",
    "CLOAKBROWSER_SOURCE_PATCH_V3",
    "CLOAKBROWSER_SOURCE_PATCH_V4",
    "CLOAKBROWSER_SOURCE_PATCH_V5",
    "CLOAKBROWSER_SOURCE_PATCH_V6",
    "CLOAKBROWSER_SOURCE_PATCH_V7",
    "CLOAKBROWSER_SOURCE_PATCH_V8",
)

SOURCE_RUNTIME_HELPER = f"""

# {PATCH_MARKER}: start
def _cloakbrowser_source_runtime():
    try:
        import sys as _cloakbrowser_sys
        from helpers import plugins as _cloakbrowser_plugins

        _cloakbrowser_enabled = _cloakbrowser_plugins.get_enabled_plugins(None)
        if _cloakbrowser_enabled is not None:
            _cloakbrowser_found = False
            for _cloakbrowser_item in _cloakbrowser_enabled:
                if _cloakbrowser_item == "cloakbrowser":
                    _cloakbrowser_found = True
                    break
                if isinstance(_cloakbrowser_item, dict):
                    _cloakbrowser_name = (
                        _cloakbrowser_item.get("name")
                        or _cloakbrowser_item.get("id")
                        or _cloakbrowser_item.get("plugin_name")
                    )
                else:
                    _cloakbrowser_name = (
                        getattr(_cloakbrowser_item, "name", None)
                        or getattr(_cloakbrowser_item, "id", None)
                    )
                if _cloakbrowser_name == "cloakbrowser":
                    _cloakbrowser_found = True
                    break
            if not _cloakbrowser_found:
                return None
        _cloakbrowser_dir = _cloakbrowser_plugins.find_plugin_dir("cloakbrowser")
        if not _cloakbrowser_dir:
            return None
        if _cloakbrowser_dir not in _cloakbrowser_sys.path:
            _cloakbrowser_sys.path.insert(0, _cloakbrowser_dir)
        from plugin_imports import plugin_import as _cloakbrowser_plugin_import

        return _cloakbrowser_plugin_import("helpers.source_runtime")
    except Exception as exc:
        try:
            PrintStyle.warning(f"CloakBrowser source bootstrap unavailable: {{exc}}")
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

CONTENT_HELPER_ORIGINAL = """        await self.context.add_init_script(path=str(CONTENT_HELPER_PATH))
"""

CONTENT_HELPER_PATCHED = """        if not (_cloakbrowser_runtime and _cloakbrowser_runtime.disable_shadow_dom_init()):
            await self.context.add_init_script(path=str(CONTENT_HELPER_PATH))
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

OPEN_ORIGINAL_WITH_LIMIT = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        self._ensure_can_open_page()
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

OPEN_PATCHED_WITH_LIMIT = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        self._ensure_can_open_page()
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
                    self._ensure_can_open_page()
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
                            self._ensure_can_open_page()
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


def patch_runtime_source(manifest: dict[str, Any]) -> dict[str, Any]:
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
            "timestamp": _utc_now(),
        }
        manifest["runtime_source_patch"] = result
        _record_runtime_patch(manifest, result)
        return result

    is_old_patch = any(marker in original_text for marker in OLD_PATCH_MARKERS)
    original_hash = sha256_file(target)
    patched_text = (
        upgrade_runtime_source_text(original_text)
        if is_old_patch
        else patch_runtime_source_text(original_text)
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
        "timestamp": _utc_now(),
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
    patched = _ensure_helper_block(text)
    patched = _replace_once(patched, LAUNCH_ORIGINAL, LAUNCH_PATCHED)
    patched = _replace_first_matching_pair_once(
        patched,
        (
            (SHADOW_ORIGINAL, SHADOW_PATCHED),
            (CONTENT_HELPER_ORIGINAL, CONTENT_HELPER_PATCHED),
        ),
    )
    patched = _replace_once(patched, START_PAGES_ORIGINAL, START_PAGES_PATCHED)
    patched = _replace_first_matching_pair_once(
        patched,
        (
            (OPEN_ORIGINAL_WITH_LIMIT, OPEN_PATCHED_WITH_LIMIT),
            (OPEN_ORIGINAL, OPEN_PATCHED),
        ),
    )
    patched = _replace_once(patched, CLOSE_BROWSER_ORIGINAL, CLOSE_BROWSER_PATCHED)
    patched = _replace_once(patched, CLOSE_ALL_ORIGINAL, CLOSE_ALL_PATCHED)
    patched = _replace_once(patched, CONTEXT_CLOSED_ORIGINAL, CONTEXT_CLOSED_PATCHED)
    patched = _replace_once(patched, STOP_PLAYWRIGHT_ORIGINAL, STOP_PLAYWRIGHT_PATCHED)
    return patched


def upgrade_runtime_source_text(text: str) -> str:
    patched = text
    for old_marker in OLD_PATCH_MARKERS:
        patched = patched.replace(old_marker, PATCH_MARKER)
    patched = _replace_helper_block(patched)
    patched = _replace_first_matching_once(
        patched,
        (LAUNCH_PATCHED, LAUNCH_ORIGINAL),
        LAUNCH_PATCHED,
    )
    patched = _replace_first_matching_pair_once(
        patched,
        (
            (SHADOW_PATCHED, SHADOW_PATCHED),
            (SHADOW_ORIGINAL, SHADOW_PATCHED),
            (CONTENT_HELPER_PATCHED, CONTENT_HELPER_PATCHED),
            (CONTENT_HELPER_ORIGINAL, CONTENT_HELPER_PATCHED),
        ),
    )
    if START_PAGES_PATCHED in patched:
        pass
    elif START_PAGES_PATCHED_V1 in patched:
        patched = _replace_once(patched, START_PAGES_PATCHED_V1, START_PAGES_PATCHED)
    else:
        patched = _replace_once(patched, START_PAGES_ORIGINAL, START_PAGES_PATCHED)
    patched = _replace_first_matching_pair_once(
        patched,
        (
            (OPEN_PATCHED_WITH_LIMIT, OPEN_PATCHED_WITH_LIMIT),
            (OPEN_ORIGINAL_WITH_LIMIT, OPEN_PATCHED_WITH_LIMIT),
            (OPEN_PATCHED, OPEN_PATCHED),
            (OPEN_PATCHED_V2, OPEN_PATCHED),
            (OPEN_PATCHED_V1, OPEN_PATCHED),
            (OPEN_ORIGINAL, OPEN_PATCHED),
        ),
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


def _ensure_helper_block(text: str) -> str:
    if PATCH_MARKER in text:
        updated = _replace_helper_block(text)
        if updated != text:
            return updated
        raise ValueError("Expected one CloakBrowser source helper block, found 0")
    anchor = 'CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"\n'
    return _replace_once(text, anchor, anchor + SOURCE_RUNTIME_HELPER)


def _replace_helper_block(text: str) -> str:
    pattern = rf"\n# {PATCH_MARKER}: start\n.*?\n# {PATCH_MARKER}: end\n"
    updated, count = re.subn(pattern, SOURCE_RUNTIME_HELPER, text, count=1, flags=re.DOTALL)
    if count == 1:
        return updated
    return text


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


def _replace_first_matching_pair_once(text: str, replacements: tuple[tuple[str, str], ...]) -> str:
    for old, new in replacements:
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
