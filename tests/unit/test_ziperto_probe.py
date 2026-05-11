from ci.run_ziperto_probe import looks_cloudflare_blocked


def test_looks_cloudflare_blocked_detects_interstitial():
    assert looks_cloudflare_blocked("Just a moment...", "Performance and Security by Cloudflare")
    assert looks_cloudflare_blocked("Ziperto", "Performing security verification")


def test_looks_cloudflare_blocked_allows_normal_page():
    assert not looks_cloudflare_blocked("Ziperto", "Latest releases")
