from helpers import ubol


def test_github_headers_use_token_when_available(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    headers = ubol._github_headers(accept="application/vnd.github+json")

    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_github_headers_omit_auth_when_token_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    headers = ubol._github_headers()

    assert "Authorization" not in headers
