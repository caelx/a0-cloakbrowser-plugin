# Agent-Zero CloakBrowser Plugin

CloakBrowser-backed overlay for Agent Zero's built-in Browser tool.

The plugin is installed as a normal Agent Zero GitHub plugin because `plugin.yaml`
lives at the repository root. It exposes a `Browser` tool that delegates to
Agent Zero's upstream `_browser` tool and patches only the launch boundary so
browser sessions use CloakBrowser.

## Install

In Agent Zero, use the Plugin Installer Git workflow with this repository URL.
After install, enable `CloakBrowser`, then click the plugin's **Execute** button.
Execute installs or repairs dependencies, configures display support, installs
configured extensions, syncs extension paths into `_browser`, and prints a
human-readable readiness report. It is safe to click Execute multiple times.
The equivalent noninteractive CLI setup flow is:

```text
https://github.com/caelx/a0-cloakbrowser-plugin.git
```

```bash
cd /a0/usr/plugins/cloakbrowser
python execute.py setup --noninteractive
python execute.py status
```

The built-in `_browser` plugin may be disabled in the UI if you want to avoid
duplicate Browser tool entries. CloakBrowser still relies on `_browser` runtime
code and extension configuration.

## Commands

```bash
python execute.py
python execute.py status
python execute.py setup --noninteractive
python execute.py repair --noninteractive
python execute.py uninstall --noninteractive
python execute.py status --json
```

Running `python execute.py` is the CLI equivalent of clicking Execute. Setup
installs system browser/display/font packages when `apt-get` is available,
installs pinned `cloakbrowser[geoip]`, ensures the CloakBrowser binary,
configures Xvfb, installs or updates configured extensions, and syncs extension
paths into `_browser`. Default output is human-readable; use `--json` for CI or
scripts. `repair` reruns setup over an existing install. `status` writes
diagnostics for dependencies, display, extensions, runtime patch state, and
effective config. `uninstall` removes plugin-managed setup files and leaves
profiles and browser data intact.

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
installed first. During setup, the plugin also patches Agent Zero's
`_browser/helpers/runtime.py` so the built-in Browser runtime routes launch
kwargs through CloakBrowser before `launch_persistent_context`.

The source patch is guarded by `advanced.patch_runtime_file_if_needed`, records
the original and patched file hashes plus a backup path in the install manifest,
and is restored on uninstall only when the current file still matches the
plugin-patched hash. Process-local runtime and Playwright monkey patches remain
as fallback support for smoke tests and development runs.

The runtime patch intentionally changes two `_browser` behaviors:

- The open-shadow-DOM init script is replaced with a no-op when
  `advanced.disable_shadow_dom_init_patch` is enabled. This matches the effective
  Ghostship CloakBrowser behavior.
- In headed mode, the sole initial `about:blank` page is preserved so the visible
  CloakBrowser window is not closed during `_browser` startup.
- In headed mode, `close_all` closes user pages but leaves one registered
  `about:blank` page alive. Headless mode still delegates to upstream `_browser`
  and full runtime shutdown still closes the browser process.

Launch argument filtering is always on. The plugin drops conflicting
`--disable-gpu`, duplicate explicit `--no-sandbox`, and bare
`--disable-extensions` arguments while preserving
`--disable-extensions-except` and `--load-extension`. Chromium's default
`--disable-dev-shm-usage` fallback is intentionally allowed because headed
CloakBrowser on constrained container shared memory can otherwise abort while
allocating compositor shared images. Final launch switches are deduped by switch
key, so duplicate switches such as `--no-sandbox --no-sandbox` are collapsed.

Compared with the built-in `_browser`, this plugin keeps the same Browser tool
surface but changes the launch backend, default headed display behavior,
fingerprint/screen defaults, humanization, and extension provisioning. Browser
profiles remain under Agent Zero's `tmp/browser/sessions`.

Default network and identity settings avoid external geoip resolution:
`geoip=false`, blank timezone/locale values are filled from the local process
environment when possible, `webrtc_ip_mode=disabled`, and
`fingerprint_platform=Windows`. The cookie annoyance extension update is enabled
by default during setup.

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

Execute reuses installed extensions by default. If an extension's
`update_*_on_setup` config option is enabled, Execute refreshes that extension
during setup and reports it as updated.

BPC has managed opt-ins under `bypass_paywalls_clean`: setCookie, custom sites,
and update checks default enabled. When custom sites are enabled, setup uses
BPC's upstream custom manifest so Chromium grants `*://*/*` host access.

`sync_browser_extension_paths()` owns only the current managed extension paths
for this plugin install and exact-dedupes entries. If a live image has stale
paths from an older plugin root, reset `_browser` config/browser profile data
and rerun setup.

No paid-content bypass tests are run. CI only validates installation, manifest
loading, enable/disable behavior, and launch argument inclusion.

## Uninstall

Run uninstall before deleting the plugin directory if setup was run:

```bash
python execute.py uninstall --noninteractive
```

Uninstall disables plugin-managed `_browser` extension paths, restores the
runtime source patch when the patched file hash still matches, removes
in-process patches where possible, removes plugin-managed shim/supervisor files
recorded in the install manifest, and preserves browser profiles, downloads,
screenshots, cookies, and local storage. If setup started a direct
plugin-managed Xvfb process, uninstall terminates the recorded PID after
verifying it is an Xvfb process for the recorded display.

## Validation

```bash
uv run --group dev pytest -s tests/unit
uv run --group dev pytest -s tests/integration
bash ci/run_agent_zero_integration.sh
```

Docker-backed integration requires a working Docker engine. The default Docker
integration uses `--shm-size=2g`; the CI matrix also runs a small-shm smoke with
`64m` to prove the `--disable-dev-shm-usage` fallback remains active.
See `docs/chill-penguin-crash-analysis.md` for the symbolicated production dump
evidence behind this mitigation.

The Nix flake dev shell provides Python, uv, gh, Docker client, Xvfb, Chromium
diagnostics, and native Chromium runtime libraries. Python dev tools are defined
in `pyproject.toml` under the `dev` dependency group.

The Docker integration always runs deterministic local detection checks. Set
`CLOAKBROWSER_LIVE_DETECTOR=1` to also collect live detector screenshots and
JSON artifacts for public detection, fingerprint, header, and TLS pages. Live
detector checks are artifact-producing by default, and CI enables
`CLOAKBROWSER_LIVE_DETECTOR_STRICT=1` so third-party page probe failures fail
the run. reCAPTCHA v3, 2captcha v3, and Turnstile are included in that strict
live gate. Audio FP is skipped while its endpoint serves an expired TLS
certificate.

Integration output is captured to `artifacts/agent-zero-integration.log` and
scanned for browser crash signatures including context-close warnings, asyncio
cleanup tracebacks, `TargetClosedError`, and Python tracebacks. The heavy
browsing smoke navigates 20 pages in one CloakBrowser session, captures DOM and
screenshots, verifies the session remains alive, and writes
`artifacts/heavy-browsing-results.json`.

The uninstall smoke verifies extension cleanup, masquerade removal, patch state,
and profile preservation. It records stock `_browser` launch verification as
skipped because removing the masquerade can leave no stock Playwright Chromium
installed in the Agent Zero image.
