import types
from contextlib import contextmanager
from pathlib import Path

from helpers import extensions
from helpers.extension_install import atomic_install_extension


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
        "_agent_zero_browser_config_context",
        lambda: _browser_config_context(
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
        "_agent_zero_browser_config_context",
        lambda: _browser_config_context(
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
        "_agent_zero_browser_config_context",
        lambda: _browser_config_context(
            helpers_plugins,
            lambda: {"extension_paths": [str(ubol), "/external", str(stale_cookies), str(cookies)]},
        ),
    )

    removed = extensions.disable_managed_extension_paths()

    assert removed == [str(ubol), str(stale_cookies), str(cookies)]
    assert saved["extension_paths"] == ["/external"]


def test_install_configured_extensions_skips_when_extension_disabled(monkeypatch, tmp_path):
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
    monkeypatch.setattr(extensions, "sync_browser_extension_paths", lambda cfg=None: [])
    monkeypatch.setattr(
        extensions,
        "install_ublock_origin_lite",
        lambda path, cfg: calls.append(path) or _write_manifest(path),
    )

    cfg = _extension_config(enable_ubol=False)
    manifest = {}
    installed = extensions.install_configured_extensions(cfg, manifest)

    assert installed == []
    assert calls == []
    assert manifest["extension_actions"][0]["action"] == "reused"
    assert manifest["extension_actions"][0]["enabled"] is False


def test_install_configured_extensions_updates_when_enabled(monkeypatch, tmp_path):
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

    cfg = _extension_config(enable_ubol=True)
    manifest = {}
    installed = extensions.install_configured_extensions(cfg, manifest)

    assert installed == ["ublock_origin_lite"]
    assert calls == [ubol]
    assert manifest["extension_actions"][0]["action"] == "updated"


def test_verify_extension_reconciliation_detects_disabled_managed_path(monkeypatch, tmp_path):
    ubol = tmp_path / "ubol"
    ubol.mkdir()
    (ubol / "manifest.json").write_text("{}", encoding="utf-8")
    paths = {
        "ublock_origin_lite": ubol,
        "i_still_dont_care_about_cookies": tmp_path / "cookies",
        "bypass_paywalls_clean": tmp_path / "bpc",
    }
    monkeypatch.setattr(extensions, "managed_extension_paths", lambda: paths)
    monkeypatch.setattr(
        extensions,
        "_agent_zero_browser_config_context",
        lambda: _browser_config_context(
            types.SimpleNamespace(save_plugin_config=lambda *args: None),
            lambda: {"extension_paths": [str(ubol)]},
        ),
    )

    result = extensions.verify_extension_reconciliation(_extension_config(enable_ubol=False))

    assert result["ok"] is False
    assert "ublock_origin_lite_browser_synced" in result["failed"]


def test_atomic_install_extension_restores_old_on_failure(tmp_path):
    target = tmp_path / "extension"
    target.mkdir()
    (target / "manifest.json").write_text('{"name":"old","version":"1"}', encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()

    try:
        atomic_install_extension(source, target, source_name="broken")
    except ValueError:
        pass

    assert (target / "manifest.json").read_text(encoding="utf-8") == '{"name":"old","version":"1"}'


def test_atomic_install_extension_records_provenance(tmp_path):
    target = tmp_path / "extension"
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text('{"name":"new","version":"2"}', encoding="utf-8")

    metadata = atomic_install_extension(
        source,
        target,
        source_name="source",
        config={"enabled": True},
        extra={"tag": "v2"},
    )

    assert metadata["source"] == "source"
    assert metadata["manifest_version"] == "2"
    assert metadata["sha256"]
    assert metadata["config_hash"]
    assert metadata["tag"] == "v2"


def _extension_config(*, enable_ubol: bool):
    return {
        "extensions": {
            "enable_ublock_origin_lite": enable_ubol,
            "enable_i_still_dont_care_about_cookies": False,
            "enable_bypass_paywalls_clean": False,
        },
        "ublock_origin_lite": {"enabled_rulesets": []},
    }


def _write_manifest(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text('{"name": "uBOL", "version": "2"}', encoding="utf-8")
    return {"path": str(path), "manifest_name": "uBOL", "manifest_version": "2"}


@contextmanager
def _browser_config_context(plugins, get_browser_config):
    yield plugins, get_browser_config
