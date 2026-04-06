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

    async def compliance_check_node_instance(self, node_instance_id: str):
        diff = await self.diff(node_instance_id)
        diff_dump = diff.model_dump()

        diff_dump.pop('changed')
        diff_dump.pop('added')
        diff_dump.pop('removed')
        return diff_dump

    async def compliance_check_site(self, site_name: str):

        response = {
            "nodes": {},
        }
        nodes = await self.inventory.node_instances.query(site=site_name)

        total_desired = 0
        total_observed = 0
        total_compliant = 0

        for node in nodes.items:
            compliance = await self.compliance_check_node_instance(str(node.id))
            response["nodes"][node.id] = compliance
            total_desired += compliance["total_desired"]
            total_observed += compliance["total_observed"]
            total_compliant += compliance["compliant_count"]

        response["summary"] = {
            "total_desired": total_desired,
            "total_observed": total_observed,
            "compliant_count": total_compliant,
            "compliance_percentage": round(total_compliant / total_desired * 100, 2) if total_desired > 0 else 100.0,
        }

        return response