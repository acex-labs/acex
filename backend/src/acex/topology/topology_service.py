from typing import Annotated

from acex.models.logical_node import LogicalNode
from acex.models.node import Node
from acex.models.regions import SiteRegionAssignment
from acex.topology.layer_graph import LayerGraph
from acex.topology.scope import TopologyScope
from acex_devkit.models.topology import TopologyGraph, TopologyLayer, TopologyNode, TopologyNodeKind
from fastapi import HTTPException, Query
from sqlmodel import select


class TopologyService:
    """The topology of a part of the network, over one or more layers drawn on top of each other.

    Each layer is a source of links. The nodes they link are described once, whichever layers found them.
    """

    def __init__(self, db_manager, sources: list):
        self.db = db_manager
        self.sources = {source.layer.key: source for source in sources}

    def layers(self) -> list[TopologyLayer]:
        return [source.layer for source in self.sources.values()]

    def graph(
        self,
        layers: Annotated[list[str] | None, Query()] = None,
        region: Annotated[list[str] | None, Query()] = None,
        site: str | None = None,
    ) -> TopologyGraph:
        """Links of the asked layers, all of them when none is named, with a node in the regions and site.

        Every node in scope is there, linked or not, and so is every node a link of it leads to.
        """
        keys = layers or list(self.sources)
        unknown = [key for key in keys if key not in self.sources]
        if unknown:
            raise HTTPException(
                status_code=422, detail=f"Unknown layers {unknown}; known layers are {list(self.sources)}"
            )

        session = next(self.db.get_session())
        try:
            scope = TopologyScope(session, regions=region, site=site)
            found = [self.sources[key].collect(session, scope) for key in keys]
            node_instance_ids = scope.members(session).union(*(graph.node_instance_ids() for graph in found))
            nodes = self._describe_node_instances(session, scope, node_instance_ids)
            for graph in found:
                for node in graph.nodes.values():
                    nodes.setdefault(node.id, node)
            return TopologyGraph(
                layers=keys,
                nodes=list(nodes.values()),
                links=[link for graph in found for link in graph.links.values()],
            )
        finally:
            session.close()

    @staticmethod
    def _describe_node_instances(session, scope: TopologyScope, ids: set[int]) -> dict[str, TopologyNode]:
        if not ids:
            return {}
        rows = session.exec(
            select(Node.id, LogicalNode.hostname, LogicalNode.site, LogicalNode.role)
            .join(LogicalNode, Node.logical_node_id == LogicalNode.id)
            .where(Node.id.in_(ids))
        ).all()

        sites = {row.site for row in rows if row.site}
        regions_of: dict[str, list[str]] = {}
        if sites:
            assignments = session.exec(
                select(SiteRegionAssignment)
                .where(SiteRegionAssignment.site_name.in_(sites))
                .order_by(SiteRegionAssignment.region_name)
            ).all()
            for assignment in assignments:
                regions_of.setdefault(assignment.site_name, []).append(assignment.region_name)

        nodes = {}
        for row in rows:
            node_id = LayerGraph.node_instance_id(row.id)
            nodes[node_id] = TopologyNode(
                id=node_id,
                kind=TopologyNodeKind.NODE_INSTANCE,
                label=row.hostname or node_id,
                node_instance_id=row.id,
                site=row.site,
                regions=regions_of.get(row.site, []),
                role=row.role,
                in_scope=scope.contains_site(row.site),
            )
        return nodes
