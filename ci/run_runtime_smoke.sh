#!/usr/bin/env bash
set -euo pipefail
plugin_dir="$(PYTHONPATH=/git/agent-zero /opt/venv-a0/bin/python - <<'PY'
from helpers import plugins
print(plugins.find_plugin_dir("cloakbrowser"))
PY
)"
python "$plugin_dir/ci/run_runtime_smoke.py"
