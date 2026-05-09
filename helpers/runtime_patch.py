from __future__ import annotations

import asyncio
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_STATE: dict[str, Any] = {
    "patched": False,
    "original_shadow_dom_script": None,
    "original_start": None,
}


def apply_runtime_patch() -> dict[str, Any]:
    if _STATE["patched"]:
        return status()
    try:
        with _agent_zero_import_context():
            from plugins._browser.helpers import runtime
    except Exception as exc:
        _STATE["error"] = str(exc)
        return status()

    core = runtime._BrowserRuntimeCore
    _STATE["original_shadow_dom_script"] = core._shadow_dom_script
    _STATE["original_start"] = core._start

    def _empty_shadow_dom_script() -> str:
        return "(() => {})();"

    async def _patched_start(self):
        from .config import get_config

        cfg = get_config()
        await _STATE["original_start"](self)
        if not cfg["advanced"]["preserve_headed_placeholder_page"]:
            return
        if not cfg["runtime"]["headed"]:
            return
        try:
            if self.pages:
                return
            context_pages = list(getattr(self.context, "pages", []) or [])
            if len(context_pages) == 1 and context_pages[0].url == "about:blank":
                await self._register_page(context_pages[0])
        except Exception:
            return

    core._shadow_dom_script = staticmethod(_empty_shadow_dom_script)
    core._start = _patched_start
    _STATE["patched"] = True
    return status()


def unpatch_runtime() -> dict[str, Any]:
    if not _STATE["patched"]:
        return status()
    try:
        with _agent_zero_import_context():
            from plugins._browser.helpers import runtime

        core = runtime._BrowserRuntimeCore
        if _STATE["original_shadow_dom_script"] is not None:
            core._shadow_dom_script = _STATE["original_shadow_dom_script"]
        if _STATE["original_start"] is not None:
            core._start = _STATE["original_start"]
    except Exception as exc:
        _STATE["error"] = str(exc)
    _STATE["patched"] = False
    return status()


def status() -> dict[str, Any]:
    return {
        "patched": bool(_STATE.get("patched")),
        "patching": "process-local",
        "error": _STATE.get("error", ""),
    }


@contextmanager
def _agent_zero_import_context():
    from .config import plugin_dir

    root = plugin_dir().resolve()
    removed_entries: list[tuple[int, str]] = []
    prior_helpers = sys.modules.get("helpers")
    helpers_file = Path(getattr(prior_helpers, "__file__", "") or "")
    removed_helpers = False
    if prior_helpers is not None and helpers_file:
        try:
            removed_helpers = helpers_file.resolve().is_relative_to(root)
        except Exception:
            removed_helpers = False
    if removed_helpers:
        sys.modules.pop("helpers", None)

    for index, entry in reversed(list(enumerate(sys.path))):
        try:
            matches_root = Path(entry or ".").resolve() == root
        except Exception:
            matches_root = False
        if entry == str(root) or matches_root:
            removed_entries.append((index, entry))
            sys.path.pop(index)

    for parent in root.parents:
        if (parent / "plugins" / "_browser").is_dir() and (parent / "helpers" / "tool.py").is_file():
            parent_str = str(parent)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)
            break

    try:
        yield
    finally:
        for index, entry in sorted(removed_entries):
            sys.path.insert(min(index, len(sys.path)), entry)
        if removed_helpers and prior_helpers is not None and "helpers" not in sys.modules:
            sys.modules["helpers"] = prior_helpers
