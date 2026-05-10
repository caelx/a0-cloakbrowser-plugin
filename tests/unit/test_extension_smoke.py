from ci.run_extension_smoke import probe_urls_for_static_match


def test_probe_urls_prefer_installed_static_rule_domain():
    urls = probe_urls_for_static_match(
        {"matched": True, "domains": ["3lift.com"], "ruleset": "easylist"}
    )

    assert urls[0] == "https://3lift.com/cloakbrowser-ad-probe.gif"
    assert "https://ad.doubleclick.net/cloakbrowser-ad-probe.gif" in urls


def test_probe_urls_fall_back_when_static_match_has_no_domain():
    urls = probe_urls_for_static_match({"matched": False})

    assert urls[0] == "https://3lift.com/cloakbrowser-ad-probe.gif"
