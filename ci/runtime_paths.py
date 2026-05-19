from __future__ import annotations

import sys
from pathlib import Path


def bootstrap() -> Path:
    """Make Agent Zero and this plugin importable in image and live layouts."""

    plugin_dir = Path(__file__).resolve().parents[1]
    agent_zero_dir = _agent_zero_dir(plugin_dir)
    path = str(agent_zero_dir)
    if path not in sys.path:
        sys.path.insert(0, path)
    return agent_zero_dir


def _agent_zero_dir(plugin_dir: Path) -> Path:
    for candidate in (
        Path("/a0"),
        Path("/git/agent-zero"),
        plugin_dir.parents[2] if len(plugin_dir.parents) > 2 else None,
    ):
        if candidate and (candidate / "plugins" / "_browser").is_dir():
            return candidate
    return Path("/a0")
