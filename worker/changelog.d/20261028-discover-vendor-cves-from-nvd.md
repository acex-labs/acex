---
kind: added
title: Discover vendor CVEs from NVD in background jobs
---
Workers handle `acex.cve.discover` jobs, fetch paginated NVD results for a vendor
and optional date range, and ingest them through the backend API. Requests use
rate limiting and retries.

The worker fetches the optional NVD API key from the backend once per discovery
job. Without a key, it uses NVD's lower request rate; it does not read
`NVD_API_KEY` from its environment.
