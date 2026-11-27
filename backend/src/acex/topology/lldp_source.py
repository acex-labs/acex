from acex.models.lldp_neighbor import LldpNeighbor
from acex.topology.layer_graph import LayerGraph
from acex_devkit.models.topology import TopologyEndpoint, TopologyLayer, TopologyLink, TopologyNode, TopologyNodeKind
from sqlmodel import or_, select


class LldpTopologySource:
    """Links as the devices report them over LLDP and CDP.

    A link between two devices is usually reported from both ends; it is one link here. A neighbour that is not
    in the inventory becomes an unmanaged node named by what the device reported.
    """

    layer = TopologyLayer(
        key="lldp",
        label="LLDP/CDP",
        description="Neighbours as the devices last reported them over LLDP or CDP.",
    )

    def collect(self, session, scope) -> LayerGraph:
        statement = select(LldpNeighbor).order_by(LldpNeighbor.node_instance_id, LldpNeighbor.local_interface)
        in_scope = scope.node_ids()
        if in_scope is not None:
            statement = statement.where(
                or_(LldpNeighbor.node_instance_id.in_(in_scope), LldpNeighbor.remote_node_id.in_(in_scope))
            )

        graph = LayerGraph()
        for row in session.exec(statement).all():
            if row.remote_node_id is not None:
                remote = LayerGraph.node_instance_id(row.remote_node_id)
            else:
                remote = f"unmanaged:{row.remote_device}"
                graph.add_node(
                    TopologyNode(id=remote, kind=TopologyNodeKind.UNMANAGED, label=row.remote_device, in_scope=True)
                )
            local = LayerGraph.node_instance_id(row.node_instance_id)
            graph.add_link(
                TopologyLink(
                    id="",
                    layer=self.layer.key,
                    a=TopologyEndpoint(node=local, interface=row.local_interface),
                    b=TopologyEndpoint(node=remote, interface=row.remote_interface),
                    attributes={"protocol": row.discovery_protocol, "collected_at": row.collected_at},
                )
            )
        return graph
