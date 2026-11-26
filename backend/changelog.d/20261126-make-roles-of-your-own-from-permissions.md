---
kind: added
title: Make roles of your own from the permissions of the API
audience: admin
---
The routes that read a device login in the clear, run commands on devices, read what they answered and hand out the broker's login each need a named permission (`credentials.reveal`, `operations.execute`, `operations.apply`, `workers.connect` and so on, eleven in all). The framework says which route needs which; the roles that hold them are yours to make.

In Keycloak the permissions are client roles of the client `acex`: import them with `python -m acex.permissions keycloak` (Realm settings, Action, Partial import), make a realm role of the ones it should hold, and a token carries them. Where that is not possible, `ACEX_AUTHZ_BUNDLES` names roles and what each holds, for example `ACEX_AUTHZ_BUNDLES='{"network-operator": ["operations.inspect", "operations.runs.read"]}'`. A permission that does not exist stops the API at startup with a message that names it.

`acex-admin` and `acex-service` keep working as before and are two such roles that come with the framework, under the names of `ACEX_AUTHZ_ADMIN_ROLE` and `ACEX_AUTHZ_SERVICE_ROLE`. One thing is different from the first version of the checks of operations: a worker's service account can now also list workflow runs and read their steps, since `workflows.runs.read` covers all of it. `GET /api/v1/auth/permissions` lists the permissions and the roles of the installation, and the description of each route names its permission.
