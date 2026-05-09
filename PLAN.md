# Codex Plan Mode Feature Spec: CloakBrowser Agent Zero Browser Overlay Plugin

## Repository

Repository: `a0-cloakbrowser-plugin`, a new GitHub repository.

This repository must be installable through Agent Zero’s normal GitHub plugin installer workflow. The runtime `plugin.yaml` must live at the repository root. Do not create a stripped release package path; tests, CI files, planning docs, and helper scripts may remain in the repository and may be installed with the plugin. Runtime code must not import or depend on test-only files.

Before editing, Codex must inspect:

- The current `agent0ai/agent-zero` repository, especially `plugins/_browser`, `plugins/_plugin_installer`, plugin developer documentation, and current test patterns.
- The current `caelx/ghostship-agent-zero` repository, especially the CloakBrowser install scripts, Playwright shim, browser runtime patch, extension install scripts, Docker/Xvfb setup, and image tests.
- The current `a0-community-plugins/camofox-plugin` repository, especially setup/config conventions and display dependency handling.
- The current `CloakHQ/CloakBrowser` repository and package API.
- The Bypass Paywalls Clean GitFlic source and installation instructions described below.

Follow all discovered upstream conventions, including `AGENTS.md`, `PLANS.md`, README files, contributor docs, existing tests, examples, build config, naming patterns, error handling, and validation commands.

## Goal

Create a first-class Agent Zero plugin named `CloakBrowser` that overlays Agent Zero’s built-in `_browser` plugin and makes CloakBrowser the browser implementation while preserving the full Agent Zero Browser tool behavior.

After this feature, a user can install the plugin through the normal Agent Zero GitHub plugin workflow, enable the CloakBrowser plugin, optionally disable the default `_browser` plugin UI/tool, run plugin setup, and use the normal Agent Zero `Browser` tool backed by CloakBrowser.

The plugin must translate the working CloakBrowser implementation from `ghostship-agent-zero` into a reversible Agent Zero plugin. It must install the required Xvfb/display runtime, fonts, browser libraries, CloakBrowser package/binary, Playwright shim, minimal `_browser` runtime patch, and supported browser extensions. It must also support clean uninstall/restore of original browser behavior.

## User-Visible Behavior

When installed and set up:

- Agent Zero exposes a normal `Browser` tool through the CloakBrowser plugin.
- The `Browser` tool supports the same practical action surface as Agent Zero’s built-in `_browser` `Browser` tool.
- Browser actions continue to use Agent Zero’s native browser tooling and web browsing behavior, including refs, content extraction, screenshots, navigation, keyboard/mouse actions, uploads, clipboard, multi-call behavior, profile paths, downloads, screenshots, page registration, and close behavior.
- Browser launches use CloakBrowser instead of stock Playwright Chromium.
- The default display, viewport, screen, and fingerprint dimensions are `1920x1080`.
- The viewport and display/fingerprint dimensions are configurable in plugin settings.
- The plugin reuses an existing usable Xvfb/display when possible, including a CamoFox/Camoufox-provided display, and creates a plugin-managed Xvfb only when needed.
- The plugin supports three optional browser extensions:
  - uBlock Origin Lite
  - I still don’t care about cookies
  - Bypass Paywalls Clean
- Each supported extension has independent install, enable, update/reinstall, and uninstall/disable controls.
- The plugin provides setup, status, repair, and uninstall/restore actions.
- Clean uninstall restores original `_browser` behavior, removes plugin-created shim/hooks/symlinks/supervisor edits where safe, disables plugin-managed extension paths, and preserves browser profiles and user data.

## Scope

Implement the full plugin in one pass, including:

1. Agent Zero plugin metadata and normal GitHub-installable repo layout.
2. Root `plugin.yaml`, `default_config.yaml`, `README.md`, `LICENSE`, `execute.py`, and `hooks.py`.
3. A `tools/browser.py` wrapper that delegates to upstream `plugins._browser.tools.browser.Browser`.
4. A reversible setup layer that installs CloakBrowser, Xvfb/display dependencies, fonts, browser libraries, extension assets, and runtime patches.
5. A Playwright boundary shim based on the working Ghostship implementation.
6. A minimal `_browser` runtime patch based on the working Ghostship implementation.
7. Settings and config UI for CloakBrowser runtime, display/viewport/fingerprint, extensions, setup status, and advanced options.
8. Installers and toggles for uBlock Origin Lite, I still don’t care about cookies, and Bypass Paywalls Clean.
9. CI that tests against latest Agent Zero image and latest CloakBrowser.
10. Dependabot configuration for pinned dependency/image/action updates.
11. Scheduled upstream canary workflow.
12. Full unit, integration, browser tool, limited detection, extension, install, and uninstall/restore tests.

## Non-Goals

Do not reimplement Agent Zero’s `_browser` action stack.

Do not create a separate primary `cloakbrowser_browse` tool family.

Do not use `agent-browser` as the backend for v1.

Do not use external dependency-management services such as Renovate.

Do not strip tests or CI files from the installed plugin directory.

Do not run heavy apt/pip/CloakBrowser setup automatically from `hooks.install()`.

Do not delete browser profiles or user data during uninstall.

Do not install CAPTCHA-solving services, proxy-rotation services, account-creation flows, unrelated provider plugins, unrelated MCP integrations, or unrelated Agent Zero refactors.

Do not add CI tests that access paid content or depend on bypassing a live paywalled site.

## Current Context

Agent Zero’s `_browser` plugin is the compatibility target. It owns the existing `Browser` tool, browser runtime, extension manager, browser config, persistent profile paths, downloads path, screenshots path, page registration, content extraction, refs, screenshots, screencast/runtime behavior, and close cleanup. CloakBrowser must preserve this behavior by delegating to upstream `_browser` and patching only the launch/runtime seams needed for CloakBrowser.

Ghostship’s CloakBrowser implementation already works. It installs `cloakbrowser[geoip]`, Playwright, Xvfb, fonts, and browser dependencies; runs a headed Xvfb display; creates a CloakBrowser Playwright masquerade path; patches Playwright `BrowserType.launch` and `launch_persistent_context`; filters unsupported `_browser`/Playwright args; substitutes CloakBrowser launch args; injects fingerprint/screen behavior; applies humanization; disables the open-shadow-DOM Browser init patch; preserves the headed `about:blank` placeholder page; stages uBlock Origin Lite and I still don’t care about cookies; and tests those behaviors in Docker.

CamoFox’s plugin is useful for Agent Zero plugin packaging and dependency setup style. It also installs display-related dependencies such as Xvfb, x11vnc, websockify, and noVNC. CloakBrowser should reuse an existing display where possible, but it does not need to own noVNC/x11vnc unless future Agent Zero UI requirements make that necessary.

Bypass Paywalls Clean is not available on the Google Chrome Web Store. The supplied installation instructions say that Chromium-based desktop browsers can install it in developer mode by loading the unpacked extension folder from a downloaded GitFlic zip. The instructions say to download the repository as a zip from GitFlic, unzip it, expect a folder named `bypass-paywalls-chrome-clean-master`, move that folder to a permanent location, go to `chrome://extensions`, enable Developer Mode, click `Load unpacked`, and select the extension folder containing `manifest.json`. The plugin must automate this “Load unpacked” installation path by downloading and extracting the zip source below, then loading the unpacked extension through Agent Zero’s browser extension path mechanism.

Bypass Paywalls Clean extension source:

    https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=bypass-paywalls-chrome-clean-master.zip

## Repository Layout

Use this repo shape:

    plugin.yaml
    default_config.yaml
    README.md
    LICENSE
    execute.py
    hooks.py
    .github/dependabot.yml

    api/
      status.py
      install.py
      extensions.py
      config.py

    tools/
      browser.py

    helpers/
      config.py
      install_manifest.py
      dependency_install.py
      xvfb.py
      patcher.py
      playwright_shim.py
      runtime_patch.py
      seed_playwright.py
      diagnostics.py
      extensions.py
      ubol.py
      chrome_store.py
      bypass_paywalls_clean.py
      uninstall.py

    extensions/
      python/
        agent_init/
        startup_migration/

    webui/
      config.html
      status.html

    ci/
      agent-zero.Dockerfile
      requirements-cloakbrowser.txt
      install_plugin_via_agent_zero.py
      run_browser_tool_smoke.py
      run_runtime_smoke.py
      run_detection_smoke.py
      run_extension_smoke.py
      run_uninstall_restore.py
      collect_versions.py
      notify_failure.py

    tests/
      unit/
      integration/

    .github/workflows/
      ci.yml
      upstream-canary.yml

    AGENTS.md
    PLANS.md
    pyproject.toml

Tests, CI, `AGENTS.md`, and `PLANS.md` may remain installed with the plugin. Runtime code must ignore them unless explicitly running tests.

## Plugin Metadata

Create `plugin.yaml` with a lowercase internal name and display title:

    name: cloakbrowser
    title: CloakBrowser
    description: CloakBrowser-backed overlay for Agent Zero’s Browser tool.
    version: 1.0.0
    settings_sections:
      - external
    per_project_config: false
    per_agent_config: false
    always_enabled: false

If upstream Agent Zero requires different settings sections or metadata fields, follow the current upstream convention while keeping the display title `CloakBrowser`.

## Installation Model

Use Agent Zero’s normal GitHub plugin install workflow.

`hooks.py` should be lightweight:

- verify the plugin is installed in a sane Agent Zero plugin path;
- initialize small plugin-owned metadata directories if needed;
- never install apt packages;
- never install CloakBrowser;
- never patch `_browser`;
- never run tests;
- never prune repo files.

Heavy setup must be explicit through `execute.py`:

    python execute.py setup
    python execute.py status
    python execute.py repair
    python execute.py uninstall

The plugin UI should expose these actions as buttons.

Setup must be idempotent and safe to rerun. It should detect current state, repair missing pieces, and avoid duplicating patches or services.

Uninstall must be explicit because Agent Zero may not call a plugin delete hook before removing the plugin directory. The README and UI must instruct users to run the plugin’s uninstall/restore action before deleting the plugin if setup has been run.

## Browser Tool Integration

`tools/browser.py` must expose a `Browser` tool compatible with Agent Zero’s built-in `Browser` tool.

The wrapper should subclass or delegate to `plugins._browser.tools.browser.Browser`. It must not copy the whole action dispatch. Its job is:

1. Ensure the CloakBrowser patch layer is installed in the current process before first browser action.
2. Optionally warn if the built-in `_browser` plugin is simultaneously enabled and may expose a duplicate Browser tool.
3. Delegate execution to upstream `_browser`’s `Browser.execute`.

This approach ensures current and future `_browser` actions remain supported unless upstream changes break the patch contract.

At minimum, tests must exercise the current upstream Browser actions:

- `open`
- `screenshot`
- `list`
- `state`
- `set_active` and aliases
- `navigate`
- `back`
- `forward`
- `reload`
- `content`
- `detail`
- `click`
- `type`
- `submit`
- `type_submit`
- `scroll`
- `evaluate`
- `key_chord`
- `hover`
- `double_click`
- `right_click`
- `drag`
- `wheel`
- `keyboard`
- `clipboard`
- `set_viewport`
- `select_option`
- `set_checked`
- `upload_file`
- `mouse`
- `multi`
- `close`
- `close_all`

If the current Agent Zero Browser tool has changed, match the current upstream behavior discovered during implementation.

## CloakBrowser Launch Patch

Translate Ghostship’s Playwright boundary shim into plugin code.

Patch Playwright’s async and sync generated `BrowserType` methods:

- `BrowserType.launch`
- `BrowserType.launch_persistent_context`

The patch must activate only when:

- the plugin is enabled;
- the browser type is Chromium;
- the executable path is missing, points to CloakBrowser, or points to the plugin-created `chromium-cloakbrowser` masquerade path;
- the plugin config does not explicitly disable the shim.

The patch must be idempotent and must store original methods so diagnostics and tests can confirm patch state. If a process-local unpatch is feasible, implement it. If not, uninstall should mark the patch disabled and require Agent Zero process restart to fully clear in-memory patches.

### Launch Argument Filtering

Filter unsupported or conflicting args provided by `_browser`/Playwright. Hard-drop these prefixes:

- `--disable-dev-shm-usage`
- `--disable-gpu`
- `--disable-extensions`

Drop exact matches and `--flag=value` variants where applicable.

Do not drop:

- `--disable-extensions-except=...`
- `--load-extension=...`

Extension loading must remain functional when extensions are enabled.

### Launch Argument Substitution

The shim must replace or set:

- `executable_path` to `cloakbrowser.ensure_binary()`;
- `headless` to plugin setting, default `False`;
- `viewport` to configured viewport, default `1920x1080`;
- `screen` to configured screen, default `1920x1080`;
- `args` to CloakBrowser-built args after filtering;
- `ignore_default_args` to CloakBrowser ignore defaults plus the filtered Agent Zero default prefixes.

Use current CloakBrowser APIs discovered during implementation. Ghostship currently relies on these concepts:

- `cloakbrowser.ensure_binary`
- CloakBrowser arg builder
- proxy resolution
- WebRTC arg resolution
- GeoIP/timezone/locale resolution
- CloakBrowser ignore-default-args list
- CloakBrowser humanization patching for browser/context/page behavior

If CloakBrowser internals changed, implement a compatibility adapter and update tests.

### Required Default CloakBrowser Args

By default, the final browser command line must include:

- `--fingerprint=<seed or generated value>`
- `--fingerprint-noise=false`
- `--fingerprint-screen-width=1920`
- `--fingerprint-screen-height=1080`

These must be configurable through plugin settings.

### Humanization

Default to `humanize: true` unless the setting disables it.

Support at least these human presets if supported by current CloakBrowser:

- `default`
- `careful`

If the selected preset is unsupported by current CloakBrowser, diagnostics should warn and fall back to `default`.

## Minimal `_browser` Runtime Patch

Translate Ghostship’s minimal `_browser` runtime patch into plugin form.

The patch must:

1. Disable or no-op Agent Zero’s `_browser` open-shadow-DOM init script by default.
2. Preserve the headed `about:blank` placeholder page when there is only one page, so headed mode does not lose the initial visible page.
3. Keep upstream `_browser` profile paths under `tmp/browser/sessions`.
4. Keep CloakBrowser launch behavior out of `_browser` runtime source.
5. Be idempotent and reversible.
6. Record original and patched file hashes in the plugin install manifest.
7. Refuse destructive restore if a patched file changed unexpectedly after setup.

Prefer process-local monkey patching when feasible. If direct file patching is required for reliable Agent Zero startup behavior, make it opt-in through setup, mark all changes, write backups, and include restore logic.

## Display, Xvfb, and Fonts

Default display settings:

    DISPLAY=:99
    Xvfb screen: 1920x1080x24
    viewport: 1920x1080
    screen: 1920x1080
    fingerprint screen: 1920x1080

The plugin must install required Linux browser/display/font dependencies in Docker/Agent Zero environments where apt is available.

Install these baseline packages, adapting names for distro availability:

- `fonts-freefont-ttf`
- `fonts-ipafont-gothic`
- `fonts-unifont`
- `fonts-liberation`
- `fonts-noto-color-emoji`
- `fonts-tlwg-loma-otf`
- `fonts-wqy-zenhei`
- `fontconfig`
- `xvfb`
- `libatk-bridge2.0-0`
- `libatk1.0-0`
- `libatspi2.0-0`
- `libcairo2`
- `libcups2`
- `libdbus-1-3`
- `libdrm2`
- `libgbm1`
- `libgtk-3-0`
- `libnspr4`
- `libnss3`
- `libpango-1.0-0`
- `libx11-6`
- `libxcb1`
- `libxcomposite1`
- `libxdamage1`
- `libxext6`
- `libxfixes3`
- `libxkbcommon0`
- `libxrandr2`
- `libxrender1`
- `libxshmfence1`
- `libasound2` or `libasound2t64`

Use distro-compatible probing for `libasound2` versus `libasound2t64`.

### Display Reuse

The plugin must treat Xvfb as a shared display resource.

Setup should:

1. Check whether `DISPLAY` is set.
2. Check whether the display is usable.
3. Check whether an existing Xvfb process or supervisor program already provides a usable display.
4. Reuse a suitable existing display, including a CamoFox/Camoufox-created display.
5. Only create a plugin-managed Xvfb service when no suitable display exists.

If creating a service, use a plugin-specific supervisor program name such as:

    [program:cloakbrowser_xvfb]
    command=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp

If `:99` is already in use and usable, reuse it. If `:99` is in use but unsuitable, allocate another display such as `:98` or `:100`, record it in the manifest, and set Agent Zero process environment accordingly.

Do not modify CamoFox/noVNC/x11vnc/websockify configuration unless the plugin explicitly created it. CloakBrowser does not need to own noVNC for v1.

## Plugin Settings

Create `default_config.yaml` with safe defaults.

Required settings:

    runtime:
      enabled: true
      headed: true
      display: ":99"
      auto_start_xvfb: true
      reuse_existing_display: true
      display_width: 1920
      display_height: 1080
      display_depth: 24
      viewport_width: 1920
      viewport_height: 1080
      cloakbrowser_cache_dir: "/opt/cloakbrowser"
      cloakbrowser_auto_update: false

    humanization:
      humanize: true
      human_preset: "default"

    identity:
      fingerprint_seed_mode: "random"
      fingerprint_seed: ""
      fingerprint_platform: ""
      fingerprint_noise: false
      fingerprint_screen_width: 1920
      fingerprint_screen_height: 1080
      storage_quota_mb: ""

    network_location:
      proxy: ""
      geoip: true
      timezone: ""
      locale: ""
      webrtc_ip_mode: "auto"
      webrtc_ip: ""

    advanced:
      extra_args: []
      filter_default_playwright_args: true
      disable_shadow_dom_init_patch: true
      preserve_headed_placeholder_page: true
      patch_runtime_file_if_needed: true

    extensions:
      install_ublock_origin_lite: true
      enable_ublock_origin_lite: true
      update_ublock_origin_lite_on_setup: false

      install_i_still_dont_care_about_cookies: true
      enable_i_still_dont_care_about_cookies: true
      update_i_still_dont_care_about_cookies_on_setup: false

      install_bypass_paywalls_clean: false
      enable_bypass_paywalls_clean: false
      update_bypass_paywalls_clean_on_setup: false

    ublock_origin_lite:
      filtering_mode: "complete"
      strict_block_mode: true
      enabled_rulesets:
        - ublock-filters
        - easylist
        - easyprivacy
        - pgl
        - adguard-spyware-url
        - block-lan
        - ublock-badware
        - urlhaus-full
        - annoyances-ai
        - annoyances-cookies
        - annoyances-notifications
        - annoyances-others
        - annoyances-overlays
        - annoyances-social
        - annoyances-widgets

Normalize all settings robustly. Empty settings should use defaults. Invalid settings should produce clear diagnostics and safe fallbacks.

## Supported Extensions

The plugin must support three optional browser extensions.

Each extension must have independent settings:

- install/uninstall;
- enable/disable;
- update/reinstall on setup;
- status/diagnostics;
- manifest validation;
- active-path validation;
- launch-arg validation.

Extension files should live under plugin-managed directories. Extension load paths should be added through Agent Zero `_browser` extension configuration or an equivalent upstream-compatible extension path mechanism.

When disabled, an extension may remain installed on disk but must not be loaded into browser launch args.

When uninstalled, remove only plugin-managed extension directories recorded in the install manifest.

### uBlock Origin Lite

Use the working Ghostship approach as the reference.

The installer should:

1. Fetch the latest uBlock Origin Lite source/tag from its upstream.
2. Locate the Chromium extension package.
3. Copy it into the plugin-managed extension root.
4. Remove unsuitable packaged manifest keys if required.
5. Enable configured rulesets in `manifest.json`.
6. Patch default filtering mode and strict-block behavior if supported by the current package layout.
7. Verify required rulesets exist.
8. Verify `manifest.json` exists.
9. Enable/disable through plugin settings.

If the uBOL package layout changes, diagnostics must fail clearly and preserve any existing working install.

### I still don’t care about cookies

Use the working Ghostship Chrome Web Store CRX extraction approach as the reference.

The installer should:

1. Download the extension CRX from the Chrome Web Store by extension ID.
2. Accept CRX2, CRX3, or ZIP payloads.
3. Extract safely with path traversal protection.
4. Verify `manifest.json` exists.
5. Copy into a plugin-managed extension directory.
6. Enable/disable through plugin settings.

The known extension ID used in Ghostship is:

    edibdbjcniadpccecjdfdjjppcpchdlm

Verify the ID and current availability during implementation.

### Bypass Paywalls Clean

Add Bypass Paywalls Clean as the third supported extension.

Use this exact extension source:

    https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=bypass-paywalls-chrome-clean-master.zip

Implement the “Load unpacked” installation flow described by the extension’s published instructions:

1. Download the zip file from the source URL above.
2. Extract it safely into a temporary directory with path traversal protection.
3. Locate the extracted folder named `bypass-paywalls-chrome-clean-master` or otherwise locate the first extracted extension root containing `manifest.json`.
4. Verify the selected extension root contains `manifest.json`.
5. Copy that extension root into a plugin-managed permanent extension directory.
6. Do not delete the plugin-managed extension directory after install because Chromium unpacked extensions require a persistent folder.
7. Enable or disable the extension through plugin settings by adding/removing the plugin-managed unpacked extension directory from the final browser extension load paths.
8. Preserve any existing working installation if download, extraction, validation, or copy fails during update.
9. Record the source URL, install timestamp, extension path, manifest name/version, and manifest permissions in plugin diagnostics.
10. Support update by re-downloading the zip, safely extracting it, validating `manifest.json`, replacing the plugin-managed extension directory atomically where possible, and reloading on the next browser launch.

Do not use the CRX installation path for Bypass Paywalls Clean in v1. The plugin must use the supplied zip source and load the unpacked extension directory, matching the installation instructions for Chrome, Microsoft Edge, Brave, and other desktop Chromium browsers that support Developer Mode `Load unpacked`.

Default settings for Bypass Paywalls Clean:

    install_bypass_paywalls_clean: false
    enable_bypass_paywalls_clean: false
    update_bypass_paywalls_clean_on_setup: false

Keep it opt-in by default.

Tests for Bypass Paywalls Clean should verify installation mechanics, manifest loading, enable/disable behavior, update behavior, diagnostics, and launch inclusion. Do not depend on accessing paid content in CI. Use local/static tests for extension presence and load behavior.

## Install Manifest

Create a plugin-managed install manifest, for example:

    /a0/usr/plugins/cloakbrowser/.cloakbrowser-install-manifest.json

Record:

- plugin version;
- setup timestamp;
- Agent Zero version/commit if detectable;
- Agent Zero image digest in CI if available;
- `_browser` runtime paths touched;
- original file hashes;
- patched file hashes;
- backup paths;
- Playwright shim hook paths;
- startup migration files created by the plugin;
- CloakBrowser Playwright symlink path;
- Xvfb/supervisor changes created by the plugin;
- display selected by setup;
- extension directories installed by the plugin;
- extension paths enabled by the plugin;
- CloakBrowser package version;
- CloakBrowser binary path;
- CloakBrowser cache path;
- setup status.

The manifest is required for safe uninstall/restore.

## Uninstall and Restore

Implement `execute.py uninstall`.

Uninstall must:

1. Restore original `_browser` runtime file from backup if current file hash matches the plugin-patched hash.
2. Refuse destructive restore if the file changed unexpectedly and print exact backup/current/hash details.
3. Remove plugin-created Playwright shim hooks, `.pth` files, startup migration files, or loader files.
4. Remove plugin-created CloakBrowser Playwright symlink only if recorded in the manifest and still points to CloakBrowser.
5. Disable plugin-managed extension paths from `_browser` extension config.
6. Optionally remove plugin-managed extension directories when requested.
7. Restore supervisor/Xvfb config only if the current file hash matches the plugin-patched hash.
8. Remove only plugin-managed Xvfb blocks, never CamoFox/noVNC/x11vnc/websockify blocks.
9. Leave all browser profiles, downloads, screenshots, cookies, local storage, and user data intact.
10. Avoid uninstalling shared apt packages or shared Python packages by default.
11. Report when an Agent Zero restart is required to clear in-memory patches.

Add `execute.py repair` to re-run setup checks and reapply missing patches without duplicating existing ones.

## Diagnostics and Status

Add status API and UI.

Diagnostics must check:

- plugin config validity;
- setup manifest state;
- current Agent Zero version/commit if detectable;
- current `_browser` patch status;
- Playwright shim status;
- whether patching is process-local or file-based;
- CloakBrowser Python package version;
- CloakBrowser binary path;
- CloakBrowser binary info;
- Xvfb command availability;
- selected display;
- display usability;
- display dimensions;
- installed fonts and browser libraries;
- browser launch smoke test;
- profile path;
- final launch args preview with sensitive values redacted;
- filtered args;
- extension install state;
- extension enable state;
- extension manifest metadata;
- uBOL ruleset/default settings state where practical;
- Bypass Paywalls Clean source URL, install path, manifest name/version, and manifest permissions;
- whether `_browser` appears enabled concurrently.

Do not log proxy credentials, cookies, local storage, session tokens, or browser profile contents.

## CI and Tests

Use GitHub Actions and Dependabot. Do not use Renovate.

### Dependabot

Add `.github/dependabot.yml`.

Track:

1. Docker image digest through `ci/agent-zero.Dockerfile`.
2. CloakBrowser PyPI package through `ci/requirements-cloakbrowser.txt`.
3. GitHub Actions versions.

Create `ci/agent-zero.Dockerfile`:

    FROM agent0ai/agent-zero:latest@sha256:<current_digest>

Create `ci/requirements-cloakbrowser.txt`:

    cloakbrowser[geoip]==<current_version>

Dependabot should open PRs for updates. Those PRs must run the full CI suite.

### GitHub Actions Workflows

Create:

    .github/workflows/ci.yml
    .github/workflows/upstream-canary.yml

`ci.yml` must run on pull requests and pushes to `main`.

`upstream-canary.yml` must run on:

    schedule: every 6 hours
    workflow_dispatch
    repository_dispatch for optional future external triggers

The upstream canary matrix must include:

1. `agent0ai/agent-zero:latest` with latest released `cloakbrowser[geoip]`.
2. `agent0ai/agent-zero:latest` with CloakBrowser GitHub `main` if installable from source.

No external signup or external dependency manager is required.

### Required CI Sequence

Each integration job must:

1. Pull latest Agent Zero image or use the pinned digest for Dependabot PR tests.
2. Record Agent Zero image digest.
3. Start an Agent Zero container with enough shared memory for browser launch.
4. Install the plugin through Agent Zero’s GitHub plugin installer path, not by manually copying files.
5. Run plugin setup through `execute.py setup --noninteractive`.
6. Run plugin status and collect diagnostics.
7. Exercise the CloakBrowser plugin `Browser` tool wrapper directly.
8. Exercise the patched upstream `_browser` runtime directly.
9. Run browser action smoke tests.
10. Run launch invariant tests.
11. Run extension install/toggle tests.
12. Run limited detection tests.
13. Run uninstall/restore.
14. Confirm stock browser behavior is restored after uninstall where practical.
15. Upload artifacts.

### Browser Tool Tests

The tests must instantiate and call the same `Browser` tool class Agent Zero uses from the CloakBrowser plugin:

    usr.plugins.cloakbrowser.tools.browser.Browser

The wrapper must delegate to upstream `_browser`.

Test on deterministic local pages, including a local/data URL page with:

- links;
- buttons;
- text inputs;
- checkbox;
- select element;
- upload input;
- contenteditable region;
- draggable elements;
- JavaScript state changes.

Exercise at minimum:

- open;
- state;
- list;
- navigate;
- content;
- detail;
- click;
- type;
- evaluate;
- set_viewport;
- screenshot;
- close;
- close_all.

Extended smoke must also exercise:

- submit;
- type_submit;
- scroll;
- key_chord;
- hover;
- double_click;
- right_click;
- drag;
- wheel;
- keyboard;
- clipboard;
- select_option;
- set_checked;
- upload_file;
- mouse;
- multi.

### Runtime Tests

Directly exercise:

    plugins._browser.helpers.runtime._BrowserRuntimeCore

Verify:

- profile path stays under `tmp/browser/sessions`;
- the process command line is CloakBrowser;
- child processes terminate after close;
- no unsupported args are present;
- extension paths are active only when enabled;
- screenshots work;
- content helper still works;
- page registration works;
- close cleans up.

### Launch Invariant Tests

Hard-fail if:

- CloakBrowser binary is not used.
- Profile path is not Agent Zero’s upstream `tmp/browser/sessions` path.
- `--headless` appears when headed mode is configured.
- `--disable-gpu` appears.
- `--disable-dev-shm-usage` appears.
- Bare `--disable-extensions` appears.
- Extension load args are absent when extensions are enabled.
- `--fingerprint` is absent.
- `--fingerprint-noise=false` is absent when default config is active.
- `--fingerprint-screen-width=1920` is absent by default.
- `--fingerprint-screen-height=1080` is absent by default.
- `window.innerWidth` does not match configured viewport width.
- `window.innerHeight` does not match configured viewport height.
- `screen.width` does not match configured fingerprint/screen width.
- `screen.height` does not match configured fingerprint/screen height.

### Extension Tests

Run extension tests in two configurations.

Enabled configuration:

- uBOL installed and enabled;
- I still don’t care about cookies installed and enabled;
- Bypass Paywalls Clean installed and enabled only in an opt-in test job/config;
- manifests exist;
- extension paths are active;
- launch args include active extension paths;
- uBOL blocks a simple ad-probe request with `ERR_BLOCKED_BY_CLIENT`.

Disabled configuration:

- extension files may exist;
- extension paths are not active;
- launch args do not include disabled extension paths.

Bypass Paywalls Clean tests must:

- download the supplied GitFlic zip source;
- safely extract it;
- find `bypass-paywalls-chrome-clean-master` or the extracted folder containing `manifest.json`;
- verify `manifest.json`;
- copy to a plugin-managed permanent extension directory;
- enable it through settings;
- confirm its extension path appears in active launch config;
- disable it through settings;
- confirm its extension path is absent from active launch config;
- update/reinstall it without corrupting an existing working install;
- avoid any live paid-content or paywall bypass test.

### Limited Detection Tests

Split detection checks into deterministic local checks and optional live probes.

Hard local checks must evaluate browser state and fail on regressions:

- `navigator.webdriver` must not be `true`.
- user agent must not contain `HeadlessChrome`.
- `window.chrome` should exist.
- `navigator.plugins.length` should be greater than zero.
- dimensions should match configured defaults.
- process args must not leak headless/default Playwright flags.

Optional scheduled live probes may run against stable detector pages. Save screenshots, console logs, page text, and parsed results as artifacts. Fail only on clear configured criteria, not on noisy third-party scoring changes.

### Uninstall/Restore Tests

After setup and browser smoke tests, run:

    python /a0/usr/plugins/cloakbrowser/execute.py uninstall --noninteractive

Then verify:

- `_browser` runtime restored or runtime patch disabled;
- plugin-created shim hooks removed;
- plugin-created CloakBrowser symlink removed;
- plugin-managed extension paths disabled;
- plugin-managed supervisor/Xvfb changes restored if created;
- browser profiles preserved;
- stock `_browser` can launch again without CloakBrowser command path where practical.

### Artifacts

Upload:

    artifacts/
      versions.json
      agent-zero-image-inspect.json
      cloakbrowser-info.txt
      plugin-status.json
      browser-command-lines.txt
      browser-tool-results.json
      runtime-smoke-results.json
      extension-results.json
      local-detection-results.json
      live-detector-results.json
      uninstall-results.json
      screenshots/
      logs/

### Failure Notification

Use GitHub-native notification.

On upstream canary failure:

- leave the workflow failed;
- create or update a GitHub issue titled `Upstream canary failure: CloakBrowser plugin compatibility`;
- include workflow URL, Agent Zero image digest, CloakBrowser version/source, failing job, short error summary, and artifact links.

Optional Slack/Discord webhooks may be supported only if secrets are configured, but must not be required.

## Implementation Planning Instructions

Before editing, Codex must inspect the source repos and write a brief implementation plan. Because this is a complex multi-step feature, Codex must create or maintain `PLANS.md` and `AGENTS.md` guidance in the repo.

Use an eval-driven implementation loop:

1. Establish baseline tests and current upstream behavior.
2. Implement one focused subsystem at a time.
3. Run relevant tests after each meaningful change.
4. Log what changed and what passed/failed.
5. Continue until all acceptance criteria pass.
6. Record surprises, decisions, and remaining risks.

Do not ask for more clarification unless a blocker cannot be resolved from the repositories. Make reasonable implementation decisions consistent with this spec.

## Validation

Codex must discover exact commands from the repo and Agent Zero environment. At minimum, validation must include:

- Python unit tests.
- Patch contract tests.
- Extension installer safety tests.
- Config normalization tests.
- Dependabot config validation where practical.
- GitHub Actions workflow syntax validation where practical.
- Docker integration test against `agent0ai/agent-zero:latest`.
- Plugin install through Agent Zero GitHub installer helper.
- `execute.py setup`.
- `execute.py status`.
- Browser tool smoke test.
- Runtime smoke test.
- Extension toggle test.
- Limited detection invariant test.
- `execute.py uninstall`.
- Restore verification.

Suggested commands from repo root:

    python -m pytest tests/unit
    python -m pytest tests/integration
    bash ci/run_agent_zero_integration.sh
    bash ci/run_upstream_canary_local.sh

If commands differ after implementation, document the actual commands in README and CI.

## Acceptance Criteria

The work is complete when:

- The repo is installable as a normal Agent Zero GitHub plugin.
- The plugin title is `CloakBrowser`.
- The plugin exposes a normal `Browser` tool that delegates to upstream `_browser`.
- The plugin setup installs CloakBrowser, Xvfb/display dependencies, fonts, browser libraries, and configured extension assets.
- Default dimensions are `1920x1080`.
- Viewport, display, and fingerprint dimensions are configurable.
- Existing usable Xvfb displays are reused when possible.
- Plugin-managed Xvfb is created only when needed and does not clobber CamoFox display/noVNC/x11vnc/websockify setup.
- Playwright launch calls are patched to use CloakBrowser.
- Unsupported `_browser`/Playwright args are filtered.
- Extension load args are preserved.
- CloakBrowser humanization, geoip, proxy/location, fingerprint, WebRTC, and storage settings are configurable.
- uBlock Origin Lite is supported and toggleable.
- I still don’t care about cookies is supported and toggleable.
- Bypass Paywalls Clean is supported and toggleable using the supplied GitFlic zip source.
- Bypass Paywalls Clean is installed as an unpacked Chromium extension by downloading the zip, extracting it safely, locating the folder containing `manifest.json`, and loading that persistent folder through the browser extension path mechanism.
- Setup is idempotent.
- Uninstall restores original browser behavior and preserves user profiles.
- CI runs full tests on PR/push.
- Dependabot tracks Agent Zero image digest, CloakBrowser PyPI version, and GitHub Actions updates.
- Scheduled canary tests latest Agent Zero image and latest CloakBrowser.
- Tests exercise the exact Browser tooling path Agent Zero uses.
- Limited detection tests run and produce artifacts.
- Canary failures notify through GitHub-native workflow failure and issue update.

## Final Response Expected from Codex

At completion, Codex should summarize:

- Files created and changed.
- How the plugin installs through Agent Zero’s GitHub plugin workflow.
- How the Browser tool delegates to `_browser`.
- How CloakBrowser launch patching works.
- How Xvfb/font/display setup works.
- How the three supported extensions are installed and toggled.
- How Bypass Paywalls Clean uses the supplied GitFlic zip source.
- How uninstall/restore works.
- What CI and Dependabot workflows were added.
- What validation commands were run and their results.
- Remaining risks, especially upstream `_browser` changes, CloakBrowser API changes, and GitFlic extension zip/source changes.
