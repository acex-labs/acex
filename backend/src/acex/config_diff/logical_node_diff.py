from acex_devkit.configdiffer.configdiffer import ConfigDiffer
from acex_devkit.configdiffer.diff import Diff
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.config_origin import ComponentOrigin


class DiffLogicalNode:
    def __init__(self, inventory, device_config_manager):
        self.inventory = inventory
        self.dcm = device_config_manager

    async def diff(self, node_instance_id: str):

        # Load actual node
        node = await self.inventory.node_instances.get(node_instance_id)

        # Get desired composed config, compiled so the components behind it are known
        compiled = await self.inventory.logical_nodes.compile(str(node.logical_node_id))
        desired_config = compiled.config_response.configuration

        # Get observed parsed composed config — none until a config has been collected and a NED parses it
        observed = await self.dcm.get_latest_config(node_instance_id, "parsed")
        has_tree = observed is not None and isinstance(observed.content, ComposedConfiguration)
        observed_config = observed.content if has_tree else ComposedConfiguration()

        # diff and return diff!
        differ = ConfigDiffer()
        diff = differ.diff(desired_config=desired_config, observed_config=observed_config)
        if has_tree and observed.metadata is not None:
            diff.unparsed = observed.metadata.unmatched
        self.trace(diff, compiled.configuration.origins())  # read after config_response, which places them

        return diff

    def trace(self, diff: Diff, origins: list[ComponentOrigin]) -> None:
        """Tie each declared difference to the config component behind it: a component to the one placed at
        or above its path, an attribute to one placed at the attribute itself, where there is one."""
        for change in diff.added + diff.changed:
            change.origin = self.inventory.node_instances.origin(change.path, origins)
            for attribute in change.changed_attributes:
                path = [*change.path, attribute.attribute_name]
                attribute.origin = next((o for o in origins if o.path == path), None)

    async def compliance_check_node_instance(self, node_instance_id: str):
        diff = await self.diff(node_instance_id)
        diff_dump = diff.model_dump()

        diff_dump.pop("changed")
        diff_dump.pop("added")
        diff_dump.pop("removed")
        diff_dump.pop("unparsed")
        return diff_dump

    async def compliance_check_site(self, site_name: str):

        response = {
            "nodes": {},
        }
        nodes = await self.inventory.node_instances.query(site=site_name)

        total_desired = 0
        total_observed = 0
        total_compliant = 0
        total_undeclared = 0
        total_unparsed = 0

        for node in nodes.items:
            compliance = await self.compliance_check_node_instance(str(node.id))
            response["nodes"][node.id] = compliance
            total_desired += compliance["total_desired"]
            total_observed += compliance["total_observed"]
            total_compliant += compliance["compliant_count"]
            total_undeclared += compliance["undeclared_count"]
            total_unparsed += compliance["unparsed_count"]

        response["summary"] = {
            "total_desired": total_desired,
            "total_observed": total_observed,
            "compliant_count": total_compliant,
            "undeclared_count": total_undeclared,
            "unparsed_count": total_unparsed,
            "compliance_percentage": round(total_compliant / total_desired * 100, 2) if total_desired > 0 else None,
        }

        return response
