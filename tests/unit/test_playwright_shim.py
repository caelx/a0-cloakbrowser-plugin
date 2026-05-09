from helpers.playwright_shim import filter_args


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
