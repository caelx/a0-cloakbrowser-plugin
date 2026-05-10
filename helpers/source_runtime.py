from __future__ import annotations

from typing import Any

from .config import get_config
from .playwright_shim import (
    _IN_CLOAK_LAUNCH,
    _cloak_launch_persistent_async,
    build_launch_overrides,
)
from .runtime_patch import _close_all_preserving_placeholder


async def launch_persistent_context(browser_type: Any, launch_kwargs: dict[str, Any]) -> Any:
    patched_kwargs, _info = build_launch_overrides(dict(launch_kwargs), persistent=True)
    user_data_dir = patched_kwargs.pop("user_data_dir")
    if "humanize" in patched_kwargs or "human_preset" in patched_kwargs:
        return await _cloak_launch_persistent_async(user_data_dir, patched_kwargs)

    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        return await browser_type.launch_persistent_context(user_data_dir, **patched_kwargs)
    finally:
        _IN_CLOAK_LAUNCH.reset(token)


def preserve_headed_placeholder() -> bool:
    cfg = get_config()
    return bool(cfg["runtime"]["headed"] and cfg["advanced"]["preserve_headed_placeholder_page"])


def disable_shadow_dom_init() -> bool:
    return bool(get_config()["advanced"]["disable_shadow_dom_init_patch"])


async def close_all_preserving_placeholder(core: Any) -> dict[str, Any]:
    return await _close_all_preserving_placeholder(core)
