---
kind: added
title: Manage CVEs and queue discovery from NVD
---
The CVE API supports paginated listing, individual retrieval, creation, updates,
and bulk ingestion, including CVSS scores and base severity. Queue background
discovery by vendor and optional date range through `/api/v1/cves/discover`.

Authenticated callers can store, retrieve, replace, or remove the optional NVD
API key through `/api/v1/cves/api_key`. The key is encrypted at rest using
`ACEX_CREDENTIALS_ENCRYPTION_KEY`.
