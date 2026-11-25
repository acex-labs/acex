---
kind: security
audience: admin
title: Reading a device login in the clear can require a role
---
Any token the API accepted could read a stored device login in the clear from `GET /api/v1/inventory/credentials/{id}/secret`, whether it was stored in the database or in Vault. The new setting `ACEX_AUTHZ_MODE` limits it to tokens that list the role `acex-admin` (people) or `acex-service` (the collection agent and the worker). It is `off` by default, so nothing changes after an upgrade. `log` lets every request through and logs the callers that `enforce` would refuse, so the roles can be given first; `enforce` answers 403 without the role. The roles are read from `realm_access.roles` and the roles of the audience client in the token; `ACEX_AUTHZ_ROLES_CLAIMS`, `ACEX_AUTHZ_ADMIN_ROLE` and `ACEX_AUTHZ_SERVICE_ROLE` change where and what. See the API FAQ for the Keycloak steps.
