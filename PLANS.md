# Plans

## CloakBrowser Plugin v1

- Build a normal GitHub-installable Agent Zero plugin named `cloakbrowser`.
- Delegate `tools/browser.py` to upstream `plugins._browser.tools.browser.Browser`.
- Patch Playwright and the minimal `_browser` runtime behavior process-locally before browser launch.
- Install CloakBrowser, display dependencies, Xvfb support, and supported unpacked extensions only through explicit setup.
- Keep setup idempotent and uninstall reversible through `.cloakbrowser-install-manifest.json`.
