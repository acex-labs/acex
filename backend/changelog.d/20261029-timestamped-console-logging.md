---
kind: added
title: Console logs include timestamps
---
The API server now includes timestamps in application and HTTP access logs.
Development mode shows INFO-level logs from all loggers; production mode keeps
ACEX logs at INFO and other application logs at WARNING.

Custom applications can enable the same process-wide logging configuration with
`AutomationEngine(configure_logging=True)`. It is disabled by default for custom
applications, preserving their existing logging configuration.
