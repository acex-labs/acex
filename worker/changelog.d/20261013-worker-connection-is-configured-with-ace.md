---
kind: added
title: Worker connection is configured with ACEX_* environment variables
audience: admin
refs: #314
---
`ACEX_BASE_URL` is the backend address (defaults to a local development address). `ACEX_CLIENT_ID` and `ACEX_CLIENT_SECRET` are the worker's service-account login; the secret is required when the backend has authentication enabled, otherwise the worker refuses to start instead of opening a browser login. `ACEX_ISSUER_URL` overrides the identity provider the backend reports, and `ACEX_VERIFY_SSL=false` turns off TLS verification.
