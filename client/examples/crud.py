"""CRUD example — list sites, fetch one, mutate it, save, delete a node instance.

Run with:  ACEX_BASE_URL=http://acex.local/ python examples/crud.py
Environment vars (only if backend auth is enabled):
    ACEX_ISSUER_URL, ACEX_CLIENT_ID, [ACEX_CLIENT_SECRET for client-credentials flow]
"""

from acex_client import Acex


def main():
    with Acex.from_env() as client:
        # Query sites with a filter
        result = client.inventory.sites.query(name="stockholm")
        if not result:
            print("No site named 'stockholm'")
            return
        site = result.items[0]
        print(f"site: id={site.id} name={site.name}")

        # Mutate and save
        site.display_name = "Stockholm HQ"
        site.save()

        # Bound sub-resource via LiveInstance
        node = client.inventory.node_instances.get(1)
        print(f"node: hostname={node.hostname} status={node.status}")

        # Action on a CollectionAgent
        agents = client.inventory.collection_agents.query(enabled=True)
        if agents:
            agent_id = agents.items[0].id
            print(
                f"manifest for agent {agent_id}:",
                client.inventory.collection_agents.manifest(id=agent_id).targets,
                "target(s)",
            )


if __name__ == "__main__":
    main()
