# Agent Preferences

- Be concise.
- Use this file as workspace memory.
- Record only short durable lessons here.

## Project Notes

- This repo is a root-layout Agent Zero community plugin; `plugin.yaml` must stay at the repository root.
- The plugin overlays upstream `_browser` and must delegate Browser actions instead of copying the action stack.
- Heavy setup belongs in `execute.py` / the Execute button, never in `hooks.install()`.
- Runtime and Playwright monkey patches are process-local; setup seeds dependencies/cache paths only.
- Keep browser profiles, downloads, screenshots, cookies, and local storage untouched during uninstall.
- Runtime code must not import test, CI, or planning files.
- Headed `close_all` intentionally leaves one registered `about:blank` page alive.
