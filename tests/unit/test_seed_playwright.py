from pathlib import Path

from helpers import seed_playwright


def test_masquerade_uses_agent_zero_cache_shape(monkeypatch, tmp_path):
    binary = tmp_path / "cloak-chrome"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    cache = tmp_path / "usr" / "plugins" / "_browser" / "playwright"
    monkeypatch.setattr(seed_playwright, "playwright_cache_dir", lambda: cache)

    target = seed_playwright.ensure_masquerade(str(binary))

    assert target == cache / "chromium-cloakbrowser" / "chrome-linux" / "chrome"
    assert next(cache.glob("chromium-*/chrome-linux/chrome")) == target
    assert target.exists()
    assert seed_playwright.remove_masquerade(str(target)) is True
    assert not target.exists()
