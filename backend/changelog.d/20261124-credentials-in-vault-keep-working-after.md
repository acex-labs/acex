---
kind: fixed
title: Credentials in Vault keep working after the Vault token has expired
---

A backend that logs in to Vault with an AppRole used to log in once, at startup. When that token expired, every credential with source `vault` answered 503 until the backend was restarted. The backend now logs in again when Vault refuses a read and the token no longer works, and tries the read once more. Several requests that meet an expired token share one new login. A refusal because the policy does not allow the path is left alone, and so are the other errors (Vault sealed or unreachable, a secret that does not exist). A backend given a static token behaves as before: the token is not renewed.

The integrations guide names the settings as they are, `ACEX_CREDENTIALS_VAULT_ADDR`, `_TOKEN`, `_ROLE_ID`, `_SECRET_ID` and `_VERIFY`.
