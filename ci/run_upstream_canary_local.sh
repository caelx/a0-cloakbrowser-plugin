#!/usr/bin/env bash
set -euo pipefail
CLOAKBROWSER_AGENT_ZERO_IMAGE=agent0ai/agent-zero:latest bash "$(dirname "$0")/run_agent_zero_integration.sh"
