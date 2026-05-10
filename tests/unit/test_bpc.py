import json

from helpers.bypass_paywalls_clean import _find_extension_root


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
