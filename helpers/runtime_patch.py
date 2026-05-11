from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_STATE: dict[str, Any] = {
    "patched": False,
    "shadow_dom_disabled": False,
    "original_shadow_dom_script": None,
    "original_start": None,
}

AGENT_ZERO_FALLBACK_DIR = Path("/git/agent-zero")


def apply_runtime_patch() -> dict[str, Any]:
    if _STATE["patched"]:
        return status()
    try:
        with _agent_zero_import_context():
            from plugins._browser.helpers import runtime
    except Exception as exc:
        _STATE["error"] = str(exc)
        return status()

    from .config import get_config

    cfg = get_config()
    core = runtime._BrowserRuntimeCore
    if cfg["advanced"]["disable_shadow_dom_init_patch"]:
        _STATE["original_shadow_dom_script"] = core._shadow_dom_script
        core._shadow_dom_script = staticmethod(_empty_shadow_dom_script)
        _STATE["shadow_dom_disabled"] = True
    else:
        _STATE["original_shadow_dom_script"] = None
        _STATE["shadow_dom_disabled"] = False
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
    _STATE["shadow_dom_disabled"] = False
    _STATE["original_start"] = None
    return status()


def status() -> dict[str, Any]:
    return {
        "patched": bool(_STATE.get("patched")),
        "patching": "process-local",
        "persistent": False,
        "shadow_dom_disabled": bool(_STATE.get("shadow_dom_disabled")),
        "close_all_patched": False,
        "error": _STATE.get("error", ""),
    }


def _empty_shadow_dom_script() -> str:
    return "(() => {})();"


@contextmanager
def _agent_zero_import_context():
    from .config import plugin_dir

    root = plugin_dir().resolve()
    removed_entries: list[tuple[int, str]] = []
    removed_modules: dict[str, Any] = {}
    for name, module in list(sys.modules.items()):
        if name != "helpers" and not name.startswith("helpers."):
            continue
        module_file = Path(getattr(module, "__file__", "") or "")
        if not module_file:
            continue
        try:
            if not module_file.resolve().is_relative_to(root):
                continue
        except Exception:
            continue
        removed_modules[name] = module
        sys.modules.pop(name, None)

    for index, entry in reversed(list(enumerate(sys.path))):
        try:
            matches_root = Path(entry or ".").resolve() == root
        except Exception:
            matches_root = False
        if entry == str(root) or matches_root:
            removed_entries.append((index, entry))
            sys.path.pop(index)

    for candidate in (*root.parents, AGENT_ZERO_FALLBACK_DIR):
        if (
            (candidate / "plugins" / "_browser").is_dir()
            and (candidate / "helpers" / "tool.py").is_file()
        ):
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            break

    try:
        yield
    finally:
        for index, entry in sorted(removed_entries):
            sys.path.insert(min(index, len(sys.path)), entry)
        for name, module in removed_modules.items():
            sys.modules.setdefault(name, module)
