"""CloakBrowser plugin Python extensions.

Keep Agent Zero's core ``extensions.python`` namespace visible if this plugin
package is imported first.
"""

import os
from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

for root in (os.environ.get("CLOAKBROWSER_AGENT_ZERO_DIR"), "/a0", "/git/agent-zero"):
    if not root:
        continue
    agent_zero_python_extensions = Path(root) / "extensions" / "python"
    if agent_zero_python_extensions.is_dir():
        path = str(agent_zero_python_extensions)
        if path not in __path__:
            __path__.append(path)
