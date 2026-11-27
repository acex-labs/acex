from acex.models.logical_node import LogicalNode
from acex.models.node import Node
from acex.models.regions import SiteRegionAssignment
from sqlmodel import select


class TopologyScope:
    """The part of the network a topology is asked for: some regions, a site, both, or the whole network.

    Names are whole names, as picked from a list. Several regions are all their sites together; a site narrows
    that to itself. A node is in scope when the site of its logical node is.
    """

    def __init__(self, session, regions: list[str] | None = None, site: str | None = None):
        self.sites = self._resolve_sites(session, regions or [], site)

    @staticmethod
    def _resolve_sites(session, regions: list[str], site: str | None) -> set[str] | None:
        if not regions and site is None:
            return None
        sites = {site} if site is not None else None
        if regions:
            in_regions = set(
                session.exec(
                    select(SiteRegionAssignment.site_name).where(SiteRegionAssignment.region_name.in_(regions))
                ).all()
            )
            sites = in_regions if sites is None else sites & in_regions
        return sites

    def node_ids(self):
        """A subquery of the ids of the node instances in scope, or None for the whole network."""
        if self.sites is None:
            return None
        return (
            select(Node.id)
            .join(LogicalNode, Node.logical_node_id == LogicalNode.id)
            .where(LogicalNode.site.in_(self.sites))
        )

    def members(self, session) -> set[int]:
        """The ids of the node instances in scope, linked or not."""
        statement = self.node_ids()
        return set(session.exec(statement if statement is not None else select(Node.id)).all())

    def contains_site(self, site: str | None) -> bool:
        return self.sites is None or site in self.sites
