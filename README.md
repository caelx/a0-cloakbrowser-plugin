# Agent-Zero CloakBrowser Plugin

CloakBrowser-backed overlay for Agent Zero's built-in Browser tool.

The plugin is installed as a normal Agent Zero GitHub plugin because `plugin.yaml`
lives at the repository root. It exposes a `Browser` tool that delegates to
Agent Zero's upstream `_browser` tool and patches only the launch boundary so
browser sessions use CloakBrowser.

## Install

In Agent Zero, use the Plugin Installer Git workflow with this repository URL.
After install, enable `CloakBrowser` and run setup:

```bash
cd /a0/usr/plugins/cloakbrowser
python execute.py setup --noninteractive
```

The built-in `_browser` plugin may be disabled in the UI if you want to avoid
duplicate Browser tool entries. CloakBrowser still relies on `_browser` runtime
code and extension configuration.

## Commands

```bash
python execute.py status
python execute.py setup --noninteractive
python execute.py repair --noninteractive
python execute.py uninstall --noninteractive
```

Setup installs system browser/display/font packages when `apt-get` is available,
installs `cloakbrowser[geoip]`, ensures the CloakBrowser binary, configures Xvfb,
installs configured extensions, and syncs extension paths into `_browser`.

`hooks.py` is intentionally lightweight and does not install packages, patch
Agent Zero, or remove files.

## Implementation

`tools/browser.py` exposes `Browser` by delegating to
`plugins._browser.tools.browser.Browser`. The plugin does not copy Agent Zero's
browser action stack; refs, screenshots, uploads, downloads, profiles, content
extraction, page registration, and close behavior remain owned by `_browser`.

Setup seeds a CloakBrowser masquerade binary into Agent Zero's Playwright cache
using the same shape `_browser` expects:

```text
usr/plugins/_browser/playwright/chromium-cloakbrowser/chrome-linux/chrome
```

That lets `_browser.helpers.playwright.get_playwright_binary(full_browser=True)`
resolve a Chromium-shaped binary without forcing stock Playwright Chromium to be
installed first. At launch time, `helpers/playwright_shim.py` still patches
Playwright's Chromium `launch` and `launch_persistent_context` methods in the
current process and replaces the executable with `cloakbrowser.ensure_binary()`.

Runtime patching is process-local. `execute.py setup` installs dependencies,
extensions, display support, and the Playwright cache masquerade; it does not
permanently rewrite Agent Zero runtime files. The Browser tool process applies
the runtime patch before first use. Diagnostics distinguish setup-installed
state from process-local patch state.

The runtime patch intentionally changes two `_browser` behaviors:

- The open-shadow-DOM init script is replaced with a no-op when
  `advanced.disable_shadow_dom_init_patch` is enabled. This matches the effective
  Ghostship CloakBrowser behavior without editing Agent Zero source files.
- In headed mode, the sole initial `about:blank` page is preserved so the visible
  CloakBrowser window is not closed during `_browser` startup.

Launch argument filtering is always on. The plugin drops conflicting
`--disable-dev-shm-usage`, `--disable-gpu`, and bare `--disable-extensions`
arguments while preserving `--disable-extensions-except` and `--load-extension`
so configured extensions still load.

Compared with the built-in `_browser`, this plugin keeps the same Browser tool
surface but changes the launch backend, default headed display behavior,
fingerprint/screen defaults, humanization, and extension provisioning. Browser
profiles remain under Agent Zero's `tmp/browser/sessions`.

## Display

Default display, viewport, screen, and fingerprint dimensions are `1920x1080`.
If `$DISPLAY` or the configured display is already usable, the plugin reuses it.
If the preferred display, normally `:99`, is occupied but unusable, setup tries
alternate displays such as `:98` and `:100` and records the selected display in
the install manifest.
When no usable display exists and supervisor is available, setup writes only:

```ini
[program:cloakbrowser_xvfb]
command=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp
```

If supervisor is unavailable, setup falls back to a direct Xvfb background
process for local development.

## Extensions

The plugin supports unpacked Chromium extension folders under
`.cloakbrowser/extensions/` and enables them through Agent Zero `_browser`
`extension_paths`.

- uBlock Origin Lite installs from `uBlockOrigin/uBOL-home`.
- I still don't care about cookies installs from the Chrome Web Store CRX for
  `edibdbjcniadpccecjdfdjjppcpchdlm`.
- Bypass Paywalls Clean is opt-in and installs from the supplied GitFlic zip:
  `https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=bypass-paywalls-chrome-clean-master.zip`.

No paid-content bypass tests are run. CI only validates installation, manifest
loading, enable/disable behavior, and launch argument inclusion.

## Uninstall

Run uninstall before deleting the plugin directory if setup was run:

```bash
python execute.py uninstall --noninteractive
```

Uninstall disables plugin-managed `_browser` extension paths, removes in-process
patches where possible, removes plugin-managed shim/supervisor files recorded in
the install manifest, and preserves browser profiles, downloads, screenshots,
cookies, and local storage.

## Validation

```bash
python -m pytest tests/unit
python -m pytest tests/integration
bash ci/run_agent_zero_integration.sh
```

Docker-backed integration requires a working Docker engine.

The Docker integration always runs deterministic local detection checks. Set
`CLOAKBROWSER_LIVE_DETECTOR=1` to also collect live detector screenshots and
JSON artifacts for public detection, fingerprint, header, and TLS pages. Live
detector checks are artifact-producing by default, and CI enables
`CLOAKBROWSER_LIVE_DETECTOR_STRICT=1` so third-party page probe failures fail
the run. reCAPTCHA v3, 2captcha v3, and Turnstile are included in that strict
live gate. Audio FP is skipped while its endpoint serves an expired TLS
certificate.
