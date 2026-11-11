from acex.models.device_config import DeviceConfigResponse
from acex_devkit.configdiffer.configdiffer import ConfigDiffer
from acex_devkit.configdiffer.diff import Diff
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.config_origin import ComponentOrigin


class DiffLogicalNode:
    def __init__(self, inventory, device_config_manager):
        self.inventory = inventory
        self.dcm = device_config_manager

    async def diff(self, node_instance_id: str) -> Diff:
        return await self.diff_against(node_instance_id, await self.observed(node_instance_id))

    async def observed(self, node_instance_id: str) -> DeviceConfigResponse | None:
        """The latest observed configuration parsed into a tree; none until a config has been collected
        and a NED parses it."""
        observed = await self.dcm.get_latest_config(node_instance_id, "parsed")
        return observed if observed is not None and isinstance(observed.content, ComposedConfiguration) else None

    async def diff_against(self, node_instance_id: str, observed: DeviceConfigResponse | None) -> Diff:
        """The node's desired configuration against `observed`; against an empty tree without one."""
        node = await self.inventory.node_instances.get(node_instance_id)

        # Desired, compiled so the components behind it are known
        compiled = await self.inventory.logical_nodes.compile(str(node.logical_node_id))
        desired_config = compiled.config_response.configuration

        observed_config = observed.content if observed is not None else ComposedConfiguration()
        diff = ConfigDiffer().diff(desired_config=desired_config, observed_config=observed_config)
        if observed is not None and observed.metadata is not None:
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
