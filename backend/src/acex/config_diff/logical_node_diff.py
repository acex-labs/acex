from acex_devkit.configdiffer.configdiffer import ConfigDiffer

class DiffLogicalNode: 

    def __init__(self, inventory, device_config_manager):
        self.inventory = inventory
        self.dcm = device_config_manager


    async def diff(self, node_instance_id: str):

        # Load actual node 
        node = await self.inventory.node_instances.get(node_instance_id)

        # Get desired composed config
        desired_config = node.logical_node.configuration

        # Get observed parsed composed config
        observed_config = await self.dcm.get_latest_config(node_instance_id, "parsed")

        # diff and return diff!
        differ = ConfigDiffer()
        diff = differ.diff(
            desired_config=desired_config,
            observed_config=observed_config
        )

        return diff