from __future__ import annotations

from helpers.extension import Extension


class CloakBrowserAgentInit(Extension):
    def execute(self, **kwargs):
        from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright
        from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch

        apply_runtime_patch()
        patch_playwright()
