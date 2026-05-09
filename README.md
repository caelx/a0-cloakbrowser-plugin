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

## Display

Default display, viewport, screen, and fingerprint dimensions are `1920x1080`.
If `$DISPLAY` or the configured display is already usable, the plugin reuses it.
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
