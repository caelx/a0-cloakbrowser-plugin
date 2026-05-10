#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${CLOAKBROWSER_AGENT_ZERO_IMAGE:-${AGENT_ZERO_IMAGE:-agent0ai/agent-zero:latest}}"
repo="${CLOAKBROWSER_PLUGIN_REPO:-file:///plugin-src}"
scope="${CLOAKBROWSER_INTEGRATION_SCOPE:-full}"
shm_size="${CLOAKBROWSER_DOCKER_SHM_SIZE:-2g}"
mkdir -p "$root/artifacts"
log="$root/artifacts/agent-zero-integration.log"

set +e
docker run --rm --shm-size="$shm_size" \
  -e CLOAKBROWSER_PLUGIN_REPO="$repo" \
  -e CLOAKBROWSER_INTEGRATION_SCOPE="$scope" \
  -e CLOAKBROWSER_LIVE_DETECTOR="${CLOAKBROWSER_LIVE_DETECTOR:-0}" \
  -e CLOAKBROWSER_LIVE_DETECTOR_STRICT="${CLOAKBROWSER_LIVE_DETECTOR_STRICT:-0}" \
  -e CLOAKBROWSER_UBOL_REQUIRE_LIVE_BLOCK="${CLOAKBROWSER_UBOL_REQUIRE_LIVE_BLOCK:-0}" \
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
    plugin_dir="$(python - <<PY
import sys
sys.path.insert(0, "/git/agent-zero")
from helpers import plugins
print(plugins.find_plugin_dir("cloakbrowser") or "")
PY
)"
    test -n "$plugin_dir"
    cd "$plugin_dir"
    ln -sfn /artifacts artifacts
    python execute.py --json
    python execute.py status --json > /artifacts/plugin-status.json
    python execute.py --json > /artifacts/plugin-execute-repeat.json
    python ci/collect_versions.py
    python ci/run_runtime_smoke.py
    python ci/run_heavy_browsing_smoke.py
    if [ "${CLOAKBROWSER_INTEGRATION_SCOPE:-full}" = "full" ]; then
      python ci/run_extension_smoke.py
      python ci/run_browser_tool_smoke.py
      python ci/run_detection_smoke.py
      if [ "${CLOAKBROWSER_LIVE_DETECTOR:-0}" = "1" ]; then
        python ci/run_live_detector_smoke.py
      fi
      python ci/run_uninstall_restore.py
    fi
  ' 2>&1 | tee "$log"
docker_status=${PIPESTATUS[0]}
set -e

python "$root/ci/scan_browser_log.py" "$log"
scan_status=$?
if [ "$docker_status" -ne 0 ]; then
  exit "$docker_status"
fi
exit "$scan_status"
