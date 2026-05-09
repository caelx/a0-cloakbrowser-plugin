import sys
import types
from pathlib import Path

from helpers import extensions


def test_sync_browser_extension_paths_uses_upstream_browser_config(monkeypatch, tmp_path):
    paths = extensions.managed_extension_paths()
    ubol = paths["ublock_origin_lite"]
    monkeypatch.setattr(extensions, "managed_extension_paths", lambda: {"ublock_origin_lite": ubol, "i_still_dont_care_about_cookies": tmp_path / "cookies", "bypass_paywalls_clean": tmp_path / "bpc"})
    monkeypatch.setattr(extensions, "_is_loadable", lambda path: path == ubol)

    saved = {}
    helpers_plugins = types.ModuleType("helpers.plugins")
    helpers_plugins.save_plugin_config = lambda name, project, agent, cfg: saved.update(cfg)
    browser_config_mod = types.ModuleType("plugins._browser.helpers.config")
    browser_config_mod.get_browser_config = lambda: {"extension_paths": ["/external", str(ubol)]}
    monkeypatch.setitem(sys.modules, "helpers.plugins", helpers_plugins)
    monkeypatch.setitem(sys.modules, "plugins._browser.helpers.config", browser_config_mod)

    active = extensions.sync_browser_extension_paths(
        {
            "extensions": {
                "enable_ublock_origin_lite": True,
                "enable_i_still_dont_care_about_cookies": False,
                "enable_bypass_paywalls_clean": False,
            }
        }
    )

    assert active == [str(ubol)]
    assert saved["extension_paths"] == ["/external", str(ubol)]
