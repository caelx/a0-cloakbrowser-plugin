# Agent Preferences

- Be concise.
- Use this file as workspace memory.
- Record only short durable lessons here.

## Project Notes

- This repo is a root-layout Agent Zero community plugin; `plugin.yaml` must stay at the repository root.
- The plugin overlays upstream `_browser` and must delegate Browser actions instead of copying the action stack.
- Heavy setup belongs in `execute.py` / the Execute button, never in `hooks.install()`.
- Agent Zero plugins install only through upstream `helpers.plugins.find_plugin_dir(name)`; do not hardcode, migrate, clean, or manage legacy Ghostship plugin roots.
- Process-local monkey patches cannot be CloakBrowser's primary integration because WebUI Execute runs `execute.py` in a separate subprocess from the Agent Zero server that owns Browser launches.
- CloakBrowser uses a lightweight removable `_browser/helpers/runtime.py` source bootstrap for durable launch/open behavior; process-local patches are supplemental only.
- Keep browser profiles, downloads, screenshots, cookies, and local storage untouched during uninstall.
- Runtime code must not import test, CI, or planning files.
- Headed runtime behavior must preserve the working `open()` recovery path for stale CloakBrowser contexts.
