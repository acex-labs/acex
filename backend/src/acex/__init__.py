"""ACE-X - Extendable Automation & Control Ecosystem.

Main public API exports.
"""
import importlib.metadata
__version__ = importlib.metadata.version("acex")

# Main API - AutomationEngine is the primary interface
from acex.automation_engine import AutomationEngine

__all__ = [
    "AutomationEngine",
    "__version__",
]
