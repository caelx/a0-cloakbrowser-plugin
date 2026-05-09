#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess

TITLE = "Upstream canary failure: CloakBrowser plugin compatibility"


def main() -> int:
    body = "\n".join(
        [
            "The CloakBrowser plugin upstream canary failed.",
            "",
            f"Workflow: {os.environ.get('GITHUB_SERVER_URL', '')}/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}",
            f"Agent Zero image: {os.environ.get('AGENT_ZERO_IMAGE', 'agent0ai/agent-zero:latest')}",
            f"CloakBrowser source: {os.environ.get('CLOAKBROWSER_SOURCE', 'pypi')}",
        ]
    )
    existing = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--search", TITLE, "--json", "number", "--jq", ".[0].number"],
        check=False,
        capture_output=True,
        text=True,
    )
    number = existing.stdout.strip()
    if number:
        subprocess.run(["gh", "issue", "comment", number, "--body", body], check=False)
    else:
        subprocess.run(["gh", "issue", "create", "--title", TITLE, "--body", body], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
