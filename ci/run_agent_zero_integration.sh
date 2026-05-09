#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${CLOAKBROWSER_AGENT_ZERO_IMAGE:-agent0ai/agent-zero:latest}"
repo="${CLOAKBROWSER_PLUGIN_REPO:-file:///plugin-src}"

docker run --rm --shm-size=2g \
  -e CLOAKBROWSER_PLUGIN_REPO="$repo" \
  -v "$root:/plugin-src:ro" \
  -v "$root/artifacts:/artifacts" \
  "$image" \
  bash -lc '
    set -euo pipefail
    . /ins/setup_venv.sh local
    mkdir -p /artifacts
    cd /a0
    python - <<PY
import sys
sys.path.insert(0, "/git/agent-zero")
from plugins._plugin_installer.helpers.install import install_from_git
from helpers import plugins
repo = "'"$repo"'"
if not plugins.find_plugin_dir("cloakbrowser"):
    print(install_from_git(repo, plugin_name="cloakbrowser"))
PY
    cd /a0/usr/plugins/cloakbrowser
    ln -sfn /artifacts artifacts
    python execute.py setup --noninteractive
    python execute.py status > /artifacts/plugin-status.json
    python ci/collect_versions.py
    python ci/run_extension_smoke.py
    python ci/run_browser_tool_smoke.py
    python ci/run_runtime_smoke.py
    python ci/run_detection_smoke.py
    python ci/run_uninstall_restore.py
  '
