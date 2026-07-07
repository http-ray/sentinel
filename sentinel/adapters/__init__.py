"""Integration adapters and the factory that wires them.

The rest of Sentinel depends only on the Protocols in ``base``; concrete mock or
real implementations are selected by :func:`get_adapters` based on config.
"""

from sentinel.adapters.base import (
    Adapters,
    GitHubAdapter,
    MetricsAdapter,
    RunbookStore,
    SlackAdapter,
)
from sentinel.adapters.factory import get_adapters

__all__ = [
    "Adapters",
    "GitHubAdapter",
    "MetricsAdapter",
    "RunbookStore",
    "SlackAdapter",
    "get_adapters",
]
