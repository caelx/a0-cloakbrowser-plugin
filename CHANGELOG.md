# Changelog

## Unreleased

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
