# Changelog

## Unreleased

- Add persistent Agent Zero `_browser` runtime source patching with manifest
  hashes/backups and guarded uninstall restore.
- Add managed Bypass Paywalls Clean setCookie, custom-sites, and update opt-ins.
- Exact-dedupe managed extension paths and document live stale-data reset.
- Preserve one headed `about:blank` tab during Browser `close_all` to avoid
  closing the visible CloakBrowser context.
- Dedupe final Chrome launch switches and gate Docker integration logs on
  browser crash signatures.
- Preserve Chromium's `--disable-dev-shm-usage` fallback and assert browser
  command lines do not emit duplicate `--no-sandbox`.
- Add a Nix dev shell and Docker heavy browsing smoke that verifies 20
  navigations in one CloakBrowser session.
- Default geoip off, WebRTC IP disabled, fingerprint platform Windows, local
  timezone/locale detection, and cookie-extension updates on setup.
- Make the upstream canary validate uBOL's installed static DNR rules instead
  of requiring flaky live ad-network blocks.
