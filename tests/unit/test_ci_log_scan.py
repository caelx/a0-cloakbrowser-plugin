from ci.scan_browser_log import find_crash_signatures


def test_crash_signature_scan_detects_browser_context_close():
    matches = find_crash_signatures("Warning: Browser context closed unexpectedly")

    assert matches == [r"Browser context closed unexpectedly"]


def test_crash_signature_scan_ignores_clean_log():
    assert find_crash_signatures("heavy browsing smoke completed") == []
