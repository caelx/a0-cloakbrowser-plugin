# Agent-Zero CloakBrowser Plugin

<img src="webui/thumbnail.png" alt="CloakBrowser plugin logo" width="160">

CloakBrowser-backed overlay for Agent Zero's built-in Browser tool.

The plugin is installed as a normal Agent Zero GitHub plugin because `plugin.yaml`
lives at the repository root. It does not expose its own Browser tool; upstream
`_browser` owns the Browser UI and action stack, while CloakBrowser patches only
the launch boundary when the plugin is enabled.

## Install

In Agent Zero, use the Plugin Installer Git workflow with this repository URL.
After install, enable `CloakBrowser`, then click the plugin's **Execute** button.
Execute installs or repairs dependencies, configures display support, installs
configured extensions, syncs extension paths into `_browser`, and prints a
human-readable readiness report. Setup is strict: it is complete only after
required runtime patches, extension reconciliation, and a real Browser launch
smoke pass. It is safe to click Execute multiple times.
The equivalent noninteractive CLI setup flow is:

```text
https://github.com/caelx/a0-cloakbrowser-plugin.git
```

```bash
plugin_dir="$(PYTHONPATH=/git/agent-zero python - <<'PY'
from helpers import plugins
print(plugins.find_plugin_dir("cloakbrowser"))
PY
)"
cd "$plugin_dir"
python execute.py setup --noninteractive
python execute.py verify --json
python execute.py status --json
```

Expected success markers are `readiness.ok = true`,
`invariants.source_patch_current = true`,
`invariants.extension_config_reconciled = true`, and
`invariants.last_launch_used_cloakbrowser = true`.

The built-in `_browser` plugin must remain enabled because it owns the Browser
tool, runtime, profiles, downloads, screenshots, and extension configuration.

## Commands

```bash
python execute.py
python execute.py status
python execute.py setup --noninteractive
python execute.py repair --noninteractive
python execute.py verify --json
python execute.py uninstall --noninteractive
python execute.py status --json
```

Running `python execute.py` is the CLI equivalent of clicking Execute. Setup
installs system browser/display/font packages when `apt-get` is available,
installs or upgrades `cloakbrowser[geoip]` above the plugin's minimum version,
preserves Agent Zero's Playwright unless it is missing, ensures the CloakBrowser binary,
configures Xvfb, installs or updates configured extensions, and syncs extension
paths into `_browser`. It then validates required patches and runs the Browser
launch verification. Default output is human-readable; use `--json` for CI or
scripts. `repair` reruns the same reconciliation over an existing install and
preserves the last known good setup if repair fails. `status` writes diagnostics
for dependencies, display, extensions, runtime patch state, launch proof,
invariants, and effective config. `uninstall` removes plugin-managed setup files
and leaves profiles and browser data intact.
If CloakBrowser is disabled in Agent Zero, `python execute.py` removes
plugin-managed runtime hooks/state instead of running setup. Image builds and
repair automation can pass `--force` to set up the plugin anyway.

`hooks.py` is intentionally lightweight. Its uninstall hook delegates to the
same cleanup path as `execute.py uninstall --remove-extensions`.

## Implementation

The plugin does not copy Agent Zero's browser action stack; refs, screenshots,
uploads, downloads, profiles, content extraction, page registration, keyboard
handling, typing, and close behavior remain owned by `_browser`.

Setup seeds a CloakBrowser masquerade binary into Agent Zero's Playwright cache
using the same shape `_browser` expects:

```text
usr/plugins/_browser/playwright/chromium-cloakbrowser/chrome-linux/chrome
```

That lets `_browser.helpers.playwright.get_playwright_binary(full_browser=True)`
resolve a Chromium-shaped binary without forcing stock Playwright Chromium to be
installed first. Setup also applies a lightweight removable source bootstrap to
upstream `_browser/helpers/runtime.py`. The bootstrap delegates only the launch
and headed lifecycle seams to this plugin when CloakBrowser is enabled; when the
plugin is disabled it returns to upstream launch behavior. When CloakBrowser is
enabled, the launch hook fails closed: if the runtime helper cannot load or the
launch cannot be routed through CloakBrowser, Browser launch fails with a
repairable error instead of silently using stock Playwright Chromium.

The source bootstrap intentionally changes only the `_browser` seams
CloakBrowser needs:

- Persistent browser launch is routed through CloakBrowser's bundled
  `launch_persistent_context_async` wrapper so humanize and CloakBrowser launch
  arguments are active.
- The open-shadow-DOM init script is replaced with a no-op when
  `advanced.disable_shadow_dom_init_patch` is enabled.
- Headed mode keeps the startup `about:blank` page and recovers if closing the
  visible browser leaves a stale context.

Annotation, input forwarding, visible tab selection, screenshots, and Browser UI
rendering remain owned by upstream `_browser`.

Launch argument filtering is always on. The plugin drops conflicting
`--disable-gpu`, duplicate explicit `--no-sandbox`, and bare
`--disable-extensions` arguments while preserving
`--disable-extensions-except` and `--load-extension`. Chromium's default
`--disable-dev-shm-usage` fallback is removed for the normal production profile;
provide at least `2 GB` of `/dev/shm` instead. Final launch switches are deduped
by switch key, so duplicate switches such as `--no-sandbox --no-sandbox` are
collapsed.

Compared with the built-in `_browser`, this plugin keeps the same Browser tool
surface but changes the launch backend, default headed display behavior,
fingerprint/screen defaults, humanization, and extension provisioning. Browser
profiles remain under Agent Zero's `tmp/browser/sessions`.

Default network and identity settings follow the old working Ghostship profile:
`geoip=true`, timezone/locale are resolved by CloakBrowser GeoIP unless
explicitly configured, `webrtc_ip_mode=auto`, and `fingerprint_platform=Windows`.
Effective timezone, locale, and exit IP are stored in status diagnostics after a
launch. If GeoIP is explicitly disabled, blank timezone/locale values fall back
to the local process environment when possible.

## Display

Default display, viewport, screen, and fingerprint dimensions are `1440x960`.
If `$DISPLAY` or the configured display is already usable, the plugin reuses it.
If the preferred display, normally `:99`, is occupied but unusable, setup tries
alternate displays such as `:98` and `:100` and records the selected display in
the install manifest.
When no usable display exists and supervisor is available, setup writes only:

```ini
[program:cloakbrowser_xvfb]
command=/usr/bin/Xvfb :99 -screen 0 1440x960x24 -nolisten tcp
```

If supervisor is unavailable, setup falls back to a direct Xvfb background
process for local development.

## Extensions

The plugin supports unpacked Chromium extension folders under
`.cloakbrowser/extensions/` and enables them through Agent Zero `_browser`
`extension_paths`. All extensions default off. Each extension has a single
`Enable <extension>` checkbox; when checked, Execute installs or updates that
extension and enables it. When unchecked, Execute removes that extension from
`_browser.extension_paths` but leaves installed files in place for reuse.

- uBlock Origin Lite installs from `uBlockOrigin/uBOL-home`.
- I still don't care about cookies installs from the Chrome Web Store CRX for
  `edibdbjcniadpccecjdfdjjppcpchdlm`.
- Bypass Paywalls Clean installs from the supplied GitFlic zip:
  `https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=bypass-paywalls-chrome-clean-master.zip`.

BPC has managed opt-ins under `bypass_paywalls_clean`: setCookie, custom sites,
and update checks default enabled. When custom sites are enabled, setup uses
BPC's upstream custom manifest so Chromium grants `*://*/*` host access.

`sync_browser_extension_paths()` owns only managed CloakBrowser extension paths
and exact-dedupes entries. Enabled extensions are mandatory invariants: setup
fails if an enabled extension is missing, not loadable, or not present in
`_browser.extension_paths`, and fails if a disabled managed extension remains
synced. Extension installers stage downloads in temporary directories, validate
manifests, move the previous install aside, atomically replace it, and restore
the previous install on failure. Status records extension source, version/tag,
tree hash, config hash, install time, and active path.

No paid-content bypass tests are run. CI only validates installation, manifest
loading, enable/disable behavior, and launch argument inclusion.

## Uninstall

Run uninstall before deleting the plugin directory if setup was run:

```bash
python execute.py uninstall --noninteractive
```

Uninstall disables plugin-managed `_browser` extension paths, restores the
upstream `_browser` runtime source from the hash-checked backup, removes
plugin-managed shim/supervisor files recorded in the install manifest, and
preserves browser profiles, downloads, screenshots, cookies, and local storage.
If setup started a direct plugin-managed Xvfb
process, uninstall terminates the recorded PID after verifying it is an Xvfb
process for the recorded display. Restart is not required for future launches.

## Validation

```bash
uv run --group dev pytest -s tests/unit
uv run --group dev pytest -s tests/integration
```

Container integration runs in GitHub CI. The default CI container uses
`--shm-size=2g`; production containers should provide at least `2 GB` of
`/dev/shm` for headed CloakBrowser, for example Docker or Podman
`--shm-size=2g`.
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
Run `ci/run_ziperto_probe.py` inside an Agent Zero image to capture
`artifacts/ziperto-probe.json` and `artifacts/ziperto-probe.png` with
Cloudflare markers, launch args, fingerprint dimensions, timezone/locale, and
active extension paths. Set `CLOAKBROWSER_ZIPERTO_STRICT=1` to make a detected
Cloudflare interstitial fail the probe.

Integration output is captured to `artifacts/agent-zero-integration.log` and
scanned for browser crash signatures including context-close warnings, asyncio
cleanup tracebacks, `TargetClosedError`, and Python tracebacks. The heavy
browsing smoke navigates 20 pages in one CloakBrowser session, captures DOM and
screenshots, verifies the session remains alive, and writes
`artifacts/heavy-browsing-results.json`.

The uninstall smoke verifies extension cleanup, masquerade removal, runtime
source restoration, patch state, and profile preservation.
