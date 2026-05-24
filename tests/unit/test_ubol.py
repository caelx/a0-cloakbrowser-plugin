import urllib.error
from types import SimpleNamespace

from helpers import ubol


def test_github_headers_use_token_when_available(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    headers = ubol._github_headers(accept="application/vnd.github+json")

    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_github_headers_omit_auth_when_token_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    headers = ubol._github_headers()

    assert "Authorization" not in headers


def test_github_headers_accept_gh_token_fallback(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "test-gh-token")

    headers = ubol._github_headers()

    assert headers["Authorization"] == "Bearer test-gh-token"


def test_latest_tag_falls_back_to_git_when_github_api_is_rate_limited(monkeypatch):
    def raise_rate_limit(*args, **kwargs):
        raise urllib.error.HTTPError(
            url=ubol.REPO_TAGS_URL,
            code=403,
            msg="rate limit exceeded",
            hdrs={},
            fp=None,
        )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            stdout=(
                "c435af refs/tags/uBOLite_2025.831.1814\n"
                "f6ce9 refs/tags/uBOLite_2025.825.1605\n"
            )
        )

    monkeypatch.setattr(ubol.urllib.request, "urlopen", raise_rate_limit)
    monkeypatch.setattr(ubol.subprocess, "run", fake_run)

    assert ubol._latest_tag() == "uBOLite_2025.831.1814"
