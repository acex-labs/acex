"""The deployable ACE-X API service.

`acex` is the library integrators build against — ConfigMaps, ConfigComponents
and the AutomationEngine. This package is the thin deployment shell around it:
it reads the environment, assembles an AutomationEngine from it and serves the
resulting ASGI app. Nothing here is part of the integrator-facing API.

Keeping the two apart also keeps the `acex` console command free for the CLI.
"""
