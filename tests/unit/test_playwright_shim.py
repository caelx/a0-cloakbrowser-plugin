from helpers.playwright_shim import _cloak_kwargs, filter_args, should_patch_launch


def test_filter_args_drops_conflicts_but_keeps_extension_flags():
    kept, dropped = filter_args(
        [
            "--disable-gpu",
            "--disable-gpu=true",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-extensions-except=/tmp/ext",
            "--load-extension=/tmp/ext",
            "--no-sandbox",
        ]
    )

    assert dropped == [
        "--disable-gpu",
        "--disable-gpu=true",
        "--disable-dev-shm-usage",
        "--disable-extensions",
    ]
    assert "--disable-extensions-except=/tmp/ext" in kept
    assert "--load-extension=/tmp/ext" in kept
    assert "--no-sandbox" in kept


def test_agent_zero_managed_browser_path_is_patched():
    assert should_patch_launch(
        {
            "executable_path": "/git/agent-zero/usr/plugins/_browser/playwright/chromium-1169/chrome-linux/chrome"
        }
    )


def test_cloak_kwargs_preserves_ignore_default_args():
    cleaned = _cloak_kwargs(
        {
            "executable_path": "/opt/cloakbrowser/chrome",
            "ignore_default_args": ["--disable-dev-shm-usage"],
            "args": ["--fingerprint=12345"],
        }
    )

    assert "executable_path" not in cleaned
    assert cleaned["ignore_default_args"] == ["--disable-dev-shm-usage"]
