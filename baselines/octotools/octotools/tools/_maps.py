"""Shared Google Maps access for the OctoTools map tools.

The tools reuse MapAgent's MapTool implementations (``mapagent.map_tools.tools``) so that the baseline and
MapAgent query Google Maps in exactly the same way. The API key is read from ``GOOGLE_MAPS_API_KEY``.
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from mapagent.map_tools import MapsClient  # noqa: E402
from mapagent.map_tools import tools as map_tools  # noqa: E402
from mapagent.usage import UsageTracker  # noqa: E402

__all__ = ["USAGE", "map_tools", "maps_client", "run"]

USAGE = UsageTracker()  # Google Maps usage, read and reset per question by solve.py
_client = None


def maps_client() -> MapsClient:
    global _client
    if _client is None:
        _client = MapsClient(usage=USAGE)
    return _client


def run(function, *args, **kwargs):
    """Run a MapTool; errors are returned to the OctoTools loop as ``[{"error": ...}]``."""
    try:
        return [function(maps_client(), *args, **kwargs)]
    except Exception as e:  # noqa: BLE001
        return [{"error": f"{type(e).__name__}: {e}"}]
