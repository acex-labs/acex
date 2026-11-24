---
kind: added
title: Vault login from Kubernetes, and a CA file for Vault's certificate
---

The backend can log in to Vault from Kubernetes, with the token of the pod's service account, so a pod needs no stored secret. Set `ACEX_CREDENTIALS_VAULT_K8S_ROLE` to the Vault role; `ACEX_CREDENTIALS_VAULT_K8S_MOUNT` (default `kubernetes`) and `ACEX_CREDENTIALS_VAULT_K8S_TOKEN_PATH` (default the standard service account path) only need setting when yours differ. The token file is read again at every login, because Kubernetes rotates it, and the backend logs in again when its Vault token has expired. If an AppRole and a Kubernetes role are both set the AppRole is used, and either goes before a static token.

`ACEX_CREDENTIALS_VAULT_VERIFY` can also be the path of a CA file, for a Vault with a private CA. It applies to Vault only: the other HTTPS calls of the backend, such as the one to the OIDC provider, keep the certificate authorities they use today. A path that does not exist stops the backend from starting.
