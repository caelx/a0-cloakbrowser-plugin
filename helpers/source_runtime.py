from __future__ import annotations

from typing import Any

from .config import get_config
from .playwright_shim import (
    _IN_CLOAK_LAUNCH,
    _cloak_launch_persistent_async,
    build_launch_overrides,
)


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


def disable_shadow_dom_init() -> bool:
    return bool(get_config()["advanced"]["disable_shadow_dom_init_patch"])
