from pathlib import Path


def test_root_plugin_metadata_is_installable():
    root = Path(__file__).resolve().parents[2]
    plugin_yaml = root / "plugin.yaml"

    assert plugin_yaml.is_file()
    assert (root / "webui" / "thumbnail.png").is_file()
    text = plugin_yaml.read_text(encoding="utf-8")
    assert "name: cloakbrowser" in text
    assert "title: CloakBrowser" in text


def test_cloakbrowser_is_not_a_browser_tool_wrapper():
    root = Path(__file__).resolve().parents[2]

    assert not (root / "tools" / "browser.py").exists()
    assert (root / "helpers" / "source_patch.py").is_file()
    assert (root / "helpers" / "patcher.py").is_file()
    assert (root / "helpers" / "source_runtime.py").is_file()
