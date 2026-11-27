---
kind: changed
title: The API checks permissions and no longer knows roles by name
breaking: true
audience: admin
---
The routes that read a device login in the clear, run commands on devices, read what they answered and hand out the broker's login each need a named permission (`credentials.reveal`, `operations.execute`, `workers.connect` and so on, twelve in all). A token holds a permission when it lists it among its roles. Which permissions go together in a role, and who gets it, is decided where the roles are made, in the identity provider. The backend names no roles.

**If `ACEX_AUTHZ_MODE` is `log` or `enforce`, act before you upgrade.** `acex-admin` and `acex-service` no longer let a token read a device login by their names, so the agents and the workers would be refused. Either of these works with the version you run now, so do it first:

- In Keycloak, create the client role `credentials.reveal` on the client `acex` and add it to `acex-admin` and to `acex-service` (Realm roles, the role, Associated roles). A token then lists the permission next to the role.
- Or set `ACEX_AUTHZ_BUNDLES='{"acex-admin": ["credentials.reveal"], "acex-service": ["credentials.reveal"]}'`, which says in the settings what the two roles hold.

`ACEX_AUTHZ_ADMIN_ROLE` and `ACEX_AUTHZ_SERVICE_ROLE` are no longer read. Remove them when you upgrade: the API does not start with one of them set while a check is on. An installation where `ACEX_AUTHZ_MODE` is `off` has nothing to do.

To make roles of your own, import the permissions into Keycloak as client roles of `acex` (`python -m acex.permissions keycloak`, then Realm settings, Action, Partial import) and make a realm role of the ones it should hold. An administrator is such a role with all of them. `GET /api/v1/auth/permissions` lists the permissions, and the description of each route in the API reference names the one it needs. See the API FAQ.
