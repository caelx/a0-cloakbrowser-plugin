import json

from helpers.bypass_paywalls_clean import _configure_bpc, _find_extension_root


def test_find_bpc_expected_root(tmp_path):
    root = tmp_path / "bypass-paywalls-chrome-clean-master"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"name": "BPC"}), encoding="utf-8")

    assert _find_extension_root(tmp_path) == root


def test_find_bpc_fallback_manifest_root(tmp_path):
    root = tmp_path / "other" / "extension"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text("{}", encoding="utf-8")

    assert _find_extension_root(tmp_path) == root


def test_configure_bpc_custom_manifest_and_optin_defaults(tmp_path):
    root = tmp_path / "bpc"
    custom = root / "custom"
    custom.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps({"host_permissions": ["https://example.test/*"]}), encoding="utf-8"
    )
    (custom / "manifest.json").write_text(
        json.dumps({"host_permissions": ["*://*/*"]}), encoding="utf-8"
    )
    (root / "background.js").write_text(
        "ext_api.storage.local.get({\n"
        "  optIn: false,\n"
        "  optInUpdate: true\n"
        "}, function (items) {});\n"
        "  if (!result.optInShown || !result.customShown || (!ext_chromium && !result.fetchShown)) {\n",
        encoding="utf-8",
    )

    _configure_bpc(
        root,
        {
            "opt_in_setcookie": True,
            "opt_in_custom_sites": True,
            "opt_in_update": True,
        },
    )

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    background = (root / "background.js").read_text(encoding="utf-8")
    assert manifest["host_permissions"] == ["*://*/*"]
    assert "  optIn: true,\n" in background
    assert "  optInUpdate: true\n" in background
    assert "if (false &&" in background
