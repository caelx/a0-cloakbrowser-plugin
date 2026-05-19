"""CloakBrowser plugin extensions.

This package can be imported before Agent Zero's own top-level ``extensions``
package when the plugin directory is early on ``sys.path``. Extend the package
path so core Agent Zero extension imports keep resolving.
"""

import os
from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

for root in (os.environ.get("CLOAKBROWSER_AGENT_ZERO_DIR"), "/a0", "/git/agent-zero"):
    if not root:
        continue
    agent_zero_extensions = Path(root) / "extensions"
    if agent_zero_extensions.is_dir():
        path = str(agent_zero_extensions)
        if path not in __path__:
            __path__.append(path)
