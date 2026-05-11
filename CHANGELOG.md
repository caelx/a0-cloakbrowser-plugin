# Changelog

## Unreleased

- Add persistent Agent Zero `_browser` runtime source patching with manifest
  hashes/backups and guarded uninstall restore.
- Add managed Bypass Paywalls Clean setCookie, custom-sites, and update opt-ins.
- Exact-dedupe managed extension paths and document live stale-data reset.
- Align headed tab close behavior with upstream `_browser`; `close_all` no
  longer preserves or respawns a plugin-managed `about:blank` tab.
- Keep CloakBrowser's unregistered startup target only until `open` turns it
  into the requested first visible Browser page, and restart once from `open`
  when an empty/stale context cannot create a new tab.
- Restore the old Ghostship CloakBrowser profile defaults: 1440x960
  display/viewport/fingerprint dimensions, GeoIP enabled, WebRTC IP auto, and
  no fixed UTC timezone fallback.
- Make `execute.py run` uninstall plugin-managed state when CloakBrowser is
  disabled unless `--force` is passed.
- Add an opt-in Ziperto probe that records Cloudflare markers, launch args,
  fingerprint dimensions, timezone/locale, extensions, and a screenshot.
- Dedupe final Chrome launch switches and gate Docker integration logs on
  browser crash signatures.
- Preserve Chromium's `--disable-dev-shm-usage` fallback and assert browser
  command lines do not emit duplicate `--no-sandbox`.
- Document that production headed CloakBrowser containers should provide at
  least `2 GB` of `/dev/shm`.
- Add a Nix dev shell and Docker heavy browsing smoke that verifies 20
  navigations in one CloakBrowser session.
- Fingerprint platform Windows and cookie-extension updates remain enabled on
  setup.
- Make the upstream canary validate uBOL's installed static DNR rules instead
  of requiring flaky live ad-network blocks.
