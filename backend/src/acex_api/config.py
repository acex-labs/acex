"""Runtime configuration for the ACE-X API service.

Settings live in the `acex` library (acex.settings) so the service and an
integrator's own app.py are configured the same way. Re-exported here for
callers that import them from the service package.
"""

from acex.settings import Settings, UnsafeConfiguration

__all__ = ["Settings", "UnsafeConfiguration"]
