# Changelog

## Unreleased

- Bump plugin version to `1.3.10`.
- Pass the GitHub Actions token into Upstream Canary integration runs and accept
  `GH_TOKEN` for uBOL GitHub API calls to avoid anonymous rate limits.
- Bump plugin version to `1.3.9`.
- Treat transient `httpbin` 5xx responses as skipped live-detector targets so
  the Upstream Canary does not fail on third-party probe outages.
- Bump plugin version to `1.3.8`.
- Force setup/verify imports to use the same Agent Zero root selected for
  source patching and drop stale cached `_browser` modules during that import.
- Bump plugin version to `1.3.7`.
- Remove duplicate enabled-state filtering from the injected Browser source
  bootstrap so the plugin runtime helper is the single source of truth for
  enabled versus disabled launch behavior.
- Bump plugin version to `1.3.6`.
- Enable the plugin in integration CI before setup so launch verification runs
  against the same enabled lifecycle used by Agent Zero.
- Bump plugin version to `1.3.5`.
- Allow setup/repair integration runs to continue after a runtime patch when no
  live Agent Zero `run_ui` process exists to restart.
- Bump plugin version to `1.3.4`.
- Prevent the Agent Zero Browser open patch from reusing CloakBrowser extension
  pages as normal browser tabs after extension startup or recovery.
- Bump plugin version to `1.3.3`.
- Launch CloakBrowser through its Patchright backend so Agent Zero Browser does
  not fall back to unpatched Playwright runtime behavior.
- Ensure setup/repair installs Patchright when it is missing while preserving
  Agent Zero's existing Playwright install.
- Bump plugin version to `1.3.2`.
- Schedule Agent Zero `run_ui` restarts 10 seconds after Execute returns so the
  UI receives structured JSON before the server reloads.
- Add lifecycle JSONL logging for browser cleanup and deferred restart
  decisions.
- Bump plugin version to `1.3.1`.
- Bump the Agent Zero `_browser` runtime source bootstrap to V12 so existing
  installs replace the old plugin-root `sys.path` injection with a deterministic
  file-based CloakBrowser import.
- Detect live stock Playwright Chrome Browser sessions, stop them during
  setup/repair, and restart Agent Zero through the actual `run_ui` supervisor
  program when takeover is incomplete.
- Remove the plugin-owned top-level `tools` package and keep plugin import
  paths behind Agent Zero paths so upstream `tools.skills_tool` imports keep
  working.
- Add live Browser takeover diagnostics to status JSON.
- Route current Agent Zero `/tmp/playwright/chromium-*` Browser launches
  through CloakBrowser.
- Bump the Agent Zero `_browser` runtime source bootstrap to V10 and repair
  markerless partial runtime patches left by older installs.
- Fail closed when CloakBrowser is enabled but launch cannot load the
  CloakBrowser runtime hook or produce CloakBrowser launch kwargs.
- Add strict runtime patch validation, extension reconciliation verification,
  launch verification, and top-level status invariants before setup is marked
  complete.
- Add `execute.py verify --json` and run it from setup/repair and integration
  CI without manual process-local patch calls.
- Auto-update CloakBrowser above the minimum supported version while preserving
  Agent Zero's Playwright unless it is missing.
- Install managed extensions atomically and record provenance, tree hashes,
  config hashes, and install timestamps.
- Preserve the last known good setup state when repair fails after a previous
  successful setup.
- Stop stale Agent Zero-managed Chrome/CloakBrowser processes after setup and
  restart Agent Zero through supervisor only when the `_browser` runtime source
  patch changed during that Execute run.
- Bump the Agent Zero `_browser` runtime source bootstrap to V9 and guard the
  current content-helper init script behind `disable_shadow_dom_init_patch`.
- Add Agent Zero lifecycle aliases for install/update/reconcile/enable/disable
  and include toggle-derived lifecycle state in JSON status and reconcile
  reports.
- Restore lightweight removable Agent Zero `_browser` runtime source bootstrap
  patching for durable Browser launch/open behavior.
- Route enabled launches through CloakBrowser's bundled launch wrapper so the
  full humanize stack is active.
- Add managed Bypass Paywalls Clean setCookie, custom-sites, and update opt-ins.
- Exact-dedupe managed extension paths.
- Remove the plugin-owned Browser wrapper so upstream `_browser` is the only
  Browser tool and owns keyboard handling, refs, tabs, screenshots, downloads,
  and profiles.
- Restore the old Ghostship CloakBrowser profile defaults: 1440x960
  display/viewport/fingerprint dimensions, GeoIP enabled, WebRTC IP auto, and
  no fixed UTC timezone fallback.
- Make `execute.py run` uninstall plugin-managed state when CloakBrowser is
  disabled unless `--force` is passed.
- Add a plugin uninstall hook that runs full cleanup before Agent Zero removes
  the canonical plugin directory.
- Add an opt-in Ziperto probe that records Cloudflare markers, launch args,
  fingerprint dimensions, timezone/locale, extensions, and a screenshot.
- Dedupe final Chrome launch switches and gate Docker integration logs on
  browser crash signatures.
- Preserve Chromium's `--disable-dev-shm-usage` fallback and assert browser
  command lines do not emit duplicate `--no-sandbox`.
- Document that production headed CloakBrowser containers should provide at
  least `2 GB` of `/dev/shm`.
- Resolve setup state through upstream `helpers.plugins.find_plugin_dir()`.
- Add a Nix dev shell and Docker heavy browsing smoke that verifies 20
  navigations in one CloakBrowser session.
- Fingerprint platform Windows and humanize remain enabled by default.
- Default all managed extensions off and replace install/update triplets with
  one enable checkbox per extension.
- Make the upstream canary validate uBOL's installed static DNR rules instead
  of requiring flaky live ad-network blocks.
