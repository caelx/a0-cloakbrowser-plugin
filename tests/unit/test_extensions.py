import types
from pathlib import Path

from helpers import extensions


def test_sync_browser_extension_paths_uses_upstream_browser_config(monkeypatch, tmp_path):
    paths = extensions.managed_extension_paths()
    ubol = paths["ublock_origin_lite"]
    monkeypatch.setattr(extensions, "managed_extension_paths", lambda: {"ublock_origin_lite": ubol, "i_still_dont_care_about_cookies": tmp_path / "cookies", "bypass_paywalls_clean": tmp_path / "bpc"})
    monkeypatch.setattr(extensions, "_is_loadable", lambda path: path == ubol)

    saved = {}
    helpers_plugins = types.SimpleNamespace(
        save_plugin_config=lambda name, project, agent, cfg: saved.update(cfg)
    )
    monkeypatch.setattr(
        extensions,
        "_agent_zero_browser_config_helpers",
        lambda: (helpers_plugins, lambda: {"extension_paths": ["/external", str(ubol)]}),
    )

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


def test_disable_managed_extension_paths_removes_upstream_browser_config(monkeypatch, tmp_path):
    ubol = tmp_path / "ubol"
    cookies = tmp_path / "cookies"
    bpc = tmp_path / "bpc"
    monkeypatch.setattr(
        extensions,
        "managed_extension_paths",
        lambda: {
            "ublock_origin_lite": ubol,
            "i_still_dont_care_about_cookies": cookies,
            "bypass_paywalls_clean": bpc,
        },
    )
    saved = {}
    helpers_plugins = types.SimpleNamespace(
        save_plugin_config=lambda name, project, agent, cfg: saved.update(cfg)
    )
    monkeypatch.setattr(
        extensions,
        "_agent_zero_browser_config_helpers",
        lambda: (
            helpers_plugins,
            lambda: {"extension_paths": [str(ubol), "/external", str(cookies)]},
        ),
    )

    removed = extensions.disable_managed_extension_paths()

    assert removed == [str(ubol), str(cookies)]
    assert saved["extension_paths"] == ["/external"]
