import types
from pathlib import Path

from helpers import extensions


def test_sync_browser_extension_paths_uses_upstream_browser_config(monkeypatch, tmp_path):
    paths = extensions.managed_extension_paths()
    ubol = paths["ublock_origin_lite"]
    stale_ubol = Path(
        "/git/agent-zero/usr/plugins/cloakbrowser/.cloakbrowser/extensions/ublock-origin-lite"
    )
    monkeypatch.setattr(
        extensions,
        "managed_extension_paths",
        lambda: {
            "ublock_origin_lite": ubol,
            "i_still_dont_care_about_cookies": tmp_path / "cookies",
            "bypass_paywalls_clean": tmp_path / "bpc",
        },
    )
    monkeypatch.setattr(extensions, "_is_loadable", lambda path: path == ubol)

    saved = {}
    helpers_plugins = types.SimpleNamespace(
        save_plugin_config=lambda name, project, agent, cfg: saved.update(cfg)
    )
    monkeypatch.setattr(
        extensions,
        "_agent_zero_browser_config_helpers",
        lambda: (
            helpers_plugins,
            lambda: {"extension_paths": ["/external", str(stale_ubol), str(ubol)]},
        ),
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


def test_sync_browser_extension_paths_dedupes_exact_paths(monkeypatch, tmp_path):
    ubol = tmp_path / "ubol"
    ubol.mkdir()
    (ubol / "manifest.json").write_text("{}", encoding="utf-8")
    paths = {
        "ublock_origin_lite": ubol,
        "i_still_dont_care_about_cookies": tmp_path / "cookies",
        "bypass_paywalls_clean": tmp_path / "bpc",
    }
    monkeypatch.setattr(extensions, "managed_extension_paths", lambda: paths)

    saved = {}
    helpers_plugins = types.SimpleNamespace(
        save_plugin_config=lambda name, project, agent, cfg: saved.update(cfg)
    )
    monkeypatch.setattr(
        extensions,
        "_agent_zero_browser_config_helpers",
        lambda: (
            helpers_plugins,
            lambda: {"extension_paths": ["/external", "/external", str(ubol)]},
        ),
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
    ubol = tmp_path / "ublock-origin-lite"
    cookies = tmp_path / "i-still-dont-care-about-cookies"
    bpc = tmp_path / "bypass-paywalls-clean"
    stale_cookies = Path(
        "/git/agent-zero/usr/plugins/cloakbrowser/.cloakbrowser/extensions/i-still-dont-care-about-cookies"
    )
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
            lambda: {"extension_paths": [str(ubol), "/external", str(stale_cookies), str(cookies)]},
        ),
    )

    removed = extensions.disable_managed_extension_paths()

    assert removed == [str(ubol), str(stale_cookies), str(cookies)]
    assert saved["extension_paths"] == ["/external"]


def test_install_configured_extensions_reuses_existing_without_update_flag(monkeypatch, tmp_path):
    calls = []
    ubol = tmp_path / "ubol"
    ubol.mkdir()
    (ubol / "manifest.json").write_text('{"name": "uBOL", "version": "1"}', encoding="utf-8")
    paths = {
        "ublock_origin_lite": ubol,
        "i_still_dont_care_about_cookies": tmp_path / "cookies",
        "bypass_paywalls_clean": tmp_path / "bpc",
    }
    monkeypatch.setattr(extensions, "managed_extension_paths", lambda: paths)
    monkeypatch.setattr(extensions, "sync_browser_extension_paths", lambda cfg=None: [str(ubol)])
    monkeypatch.setattr(
        extensions,
        "install_ublock_origin_lite",
        lambda path, cfg: calls.append(path) or _write_manifest(path),
    )

    cfg = _extension_config(update_ubol=False)
    manifest = {}
    installed = extensions.install_configured_extensions(cfg, manifest)

    assert installed == []
    assert calls == []
    assert manifest["extension_actions"][0]["action"] == "reused"


def test_install_configured_extensions_updates_when_configured(monkeypatch, tmp_path):
    calls = []
    ubol = tmp_path / "ubol"
    ubol.mkdir()
    (ubol / "manifest.json").write_text('{"name": "uBOL", "version": "1"}', encoding="utf-8")
    paths = {
        "ublock_origin_lite": ubol,
        "i_still_dont_care_about_cookies": tmp_path / "cookies",
        "bypass_paywalls_clean": tmp_path / "bpc",
    }
    monkeypatch.setattr(extensions, "managed_extension_paths", lambda: paths)
    monkeypatch.setattr(extensions, "sync_browser_extension_paths", lambda cfg=None: [str(ubol)])
    monkeypatch.setattr(
        extensions,
        "install_ublock_origin_lite",
        lambda path, cfg: calls.append(Path(path)) or _write_manifest(path),
    )

    cfg = _extension_config(update_ubol=True)
    manifest = {}
    installed = extensions.install_configured_extensions(cfg, manifest)

    assert installed == ["ublock_origin_lite"]
    assert calls == [ubol]
    assert manifest["extension_actions"][0]["action"] == "updated"


def _extension_config(*, update_ubol: bool):
    return {
        "extensions": {
            "install_ublock_origin_lite": True,
            "enable_ublock_origin_lite": True,
            "update_ublock_origin_lite_on_setup": update_ubol,
            "install_i_still_dont_care_about_cookies": False,
            "enable_i_still_dont_care_about_cookies": False,
            "update_i_still_dont_care_about_cookies_on_setup": False,
            "install_bypass_paywalls_clean": False,
            "enable_bypass_paywalls_clean": False,
            "update_bypass_paywalls_clean_on_setup": False,
        },
        "ublock_origin_lite": {"enabled_rulesets": []},
    }


def _write_manifest(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text('{"name": "uBOL", "version": "2"}', encoding="utf-8")
    return {"path": str(path), "manifest_name": "uBOL", "manifest_version": "2"}
