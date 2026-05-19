import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_plugin_extensions_namespace_preserves_agent_zero_extensions(monkeypatch, tmp_path):
    plugin_root = tmp_path / "plugin"
    plugin_extensions = plugin_root / "extensions" / "python" / "agent_init"
    plugin_extensions.mkdir(parents=True)
    (plugin_root / "extensions" / "__init__.py").write_text(
        (ROOT / "extensions" / "__init__.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (plugin_root / "extensions" / "python" / "__init__.py").write_text(
        (ROOT / "extensions" / "python" / "__init__.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (plugin_extensions / "__init__.py").write_text("", encoding="utf-8")

    agent_zero_root = tmp_path / "a0"
    core_extension = agent_zero_root / "extensions" / "python" / "message_loop_end"
    core_extension.mkdir(parents=True)
    (core_extension / "_10_organize_history.py").write_text(
        "DATA_NAME_TASK = 'organize-history'\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("CLOAKBROWSER_AGENT_ZERO_DIR", str(agent_zero_root))
    monkeypatch.syspath_prepend(str(plugin_root))
    for name in list(sys.modules):
        if name == "extensions" or name.startswith("extensions."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    importlib.import_module("extensions")
    module = importlib.import_module("extensions.python.message_loop_end._10_organize_history")

    assert module.DATA_NAME_TASK == "organize-history"
