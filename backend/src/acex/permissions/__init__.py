"""What a caller of the API may be allowed to do.

The framework names the things that can be allowed, the permissions below, and says which route needs which. It names
no roles and does not say which people or services get a permission: whoever runs an installation makes the roles in
their identity provider, each a role made of permissions, and gives them out.

A token holds a permission when one of its roles is the permission, or a pattern that covers it (`*`, or a prefix as
`operations.*`). Where the identity provider cannot make a role of permissions, `ACEX_AUTHZ_BUNDLES` names roles and
what each holds, and such a role counts as what the settings list for it.

    python -m acex.permissions table      the permissions as a table for the documentation
    python -m acex.permissions keycloak   the permissions as client roles, to import into a realm
"""

import json
import sys
from dataclasses import dataclass

#: The groups of routes that each have a mode of their own (off, log, enforce): reading a device login in the clear, and
#: everything that runs on or reads from devices through operations, workflows and workers.
CREDENTIALS = "credentials"
OPERATIONS = "operations"
MODE_SETTINGS = {CREDENTIALS: "ACEX_AUTHZ_MODE", OPERATIONS: "ACEX_AUTHZ_OPERATIONS_MODE"}


@dataclass(frozen=True)
class Permission:
    name: str
    #: What it lets a caller do, as a sentence that goes after "Allows to".
    summary: str
    group: str
    #: Hands out a login, or puts commands or configuration on devices.
    sensitive: bool = False


_ALL = (
    Permission("credentials.reveal", "read the stored login of a device in the clear", CREDENTIALS, sensitive=True),
    Permission("operations.execute", "run raw commands on devices", OPERATIONS, sensitive=True),
    Permission("operations.apply", "send a patch of configuration to devices", OPERATIONS, sensitive=True),
    # Every action registered today only reads (ping). An action that changes a device needs a permission of its own.
    Permission(
        "operations.inspect", "plan a patch and run the actions, which read from devices and change nothing", OPERATIONS
    ),
    Permission(
        "operations.runs.read",
        "list and read runs and their reports, which hold what the devices answered",
        OPERATIONS,
    ),
    Permission("operations.jobs", "list, read, queue again, cancel, delete and purge jobs", OPERATIONS),
    Permission(
        "workflows.edit",
        "create, change and delete workflow definitions, which are stored commands",
        OPERATIONS,
        sensitive=True,
    ),
    Permission("workflows.run", "start, continue, stop and delete workflow runs", OPERATIONS),
    Permission("workflows.runs.read", "read a workflow run and the artifacts its steps leave", OPERATIONS),
    Permission("workflows.runs.browse", "list workflow runs and read what the nodes answered in a step", OPERATIONS),
    Permission("workers.connect", "receive the login to the message broker", OPERATIONS, sensitive=True),
    Permission("workers.report", "report the state and the result of a job", OPERATIONS),
)

PERMISSIONS: dict[str, Permission] = {permission.name: permission for permission in _ALL}


def matches(role: str, permission: str) -> bool:
    """Whether a role of a token that is a permission, or a pattern of them, covers `permission`."""
    return role == permission or role == "*" or (role.endswith(".*") and permission.startswith(role[:-1]))


def expand(entries, where: str = "a list of permissions") -> frozenset[str]:
    """The permissions a list of names and patterns stands for. A name that is none of them, and a pattern that covers
    nothing, are mistakes that are better found when the API starts than when someone is refused."""
    if isinstance(entries, str):
        entries = [item.strip() for item in entries.split(",") if item.strip()]
    found: set[str] = set()
    for entry in entries:
        covered = {name for name in PERMISSIONS if matches(entry, name)}
        if not covered:
            raise ValueError(f"{where}: {entry!r} is not a permission. They are: {', '.join(PERMISSIONS)}")
        found |= covered
    return frozenset(found)


def resolve_bundles(bundles: dict[str, list[str]] | None = None) -> dict[str, frozenset[str]]:
    """The roles of the settings: role name to the permissions it holds. There are none unless the settings name
    some."""
    resolved: dict[str, frozenset[str]] = {}
    for name, entries in (bundles or {}).items():
        if name in PERMISSIONS or "*" in name:
            raise ValueError(
                f"ACEX_AUTHZ_BUNDLES: {name!r} is a permission or a pattern, which a token role already counts as; "
                "a bundle needs a name of its own"
            )
        resolved[name] = expand(entries, where=f"ACEX_AUTHZ_BUNDLES, role {name!r}")
    return resolved


def table() -> str:
    """The permissions as a Markdown table, for the documentation. The documentation is checked against this, so that
    it cannot say something else than the code does."""
    lines = ["| Permission | Allows to |", "|---|---|"]
    lines += [f"| `{p.name}` | {p.summary} |" for p in PERMISSIONS.values()]
    return "\n".join(lines)


def keycloak_roles(client: str = "acex") -> dict:
    """The permissions as client roles of `client`, in the format of Keycloak's partial import (Realm settings, Action,
    Partial import). A role of the realm made of some of them, a composite role, gives a token those permissions."""
    return {
        "ifResourceExists": "SKIP",
        "roles": {
            "client": {
                client: [{"name": p.name, "description": f"Allows to {p.summary}."} for p in PERMISSIONS.values()]
            }
        },
    }


def main(argv: list[str]) -> int:
    commands = {
        "table": lambda args: print(table()),
        "keycloak": lambda args: print(json.dumps(keycloak_roles(args[0] if args else "acex"), indent=2)),
    }
    if not argv or argv[0] not in commands:
        print(__doc__, file=sys.stderr)
        return 2
    commands[argv[0]](argv[1:])
    return 0
