from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def install():
    root = Path(__file__).resolve().parent
    if root.name != "cloakbrowser":
        # Git installs should land in Agent Zero's canonical usr/plugins root.
        pass
    (root / ".cloakbrowser" / "extensions").mkdir(parents=True, exist_ok=True)
    (root / ".cloakbrowser" / "playwright").mkdir(parents=True, exist_ok=True)
    return True


def uninstall():
    from plugin_imports import plugin_import

    plugin_import("helpers.uninstall").uninstall(remove_extensions=True)
    return True


def get_plugin_config(default=None, **kwargs):
    from plugin_imports import plugin_import

    return plugin_import("helpers.config").normalize_config(default if isinstance(default, dict) else {})


def save_plugin_config(settings=None, **kwargs):
    from plugin_imports import plugin_import

    return plugin_import("helpers.config").normalize_config(settings if isinstance(settings, dict) else {})
