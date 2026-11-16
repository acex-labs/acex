from acex.models import Asset, AssetCluster, Contact, LogicalNode, ManagementConnection, Node, Region, Site
from acex_devkit.models.node_response import AssetRefType
from acex_devkit.models.search import SearchGroup, SearchHit, SearchHitType, SearchResponse
from sqlalchemy import case, func, or_, select


class SearchTarget:
    """One kind of inventory object, and the columns a search text is looked for in.

    Matching is a case-insensitive contains on every field, built from SQLAlchemy
    operators only so it holds on every database ACEX runs on. Fields are listed
    most identifying first; hits rank by the first field they match in, and within
    it exact matches before prefix matches before the rest.
    """

    def __init__(self, type: SearchHitType, model, label, fields: dict, sublabel: tuple = (), joins: tuple = ()):
        self.type = type
        self.model = model
        self.label = label
        self.fields = fields
        self.sublabel = sublabel
        self.joins = joins

    def search(self, session, q: str, limit: int) -> SearchGroup:
        columns = list(self.fields.values())
        match = or_(*(c.icontains(q, autoescape=True) for c in columns))
        total = session.execute(self.statement(func.count(self.model.id)).where(match)).scalar_one()
        if not total:
            return SearchGroup(type=self.type, total=0, items=[])

        # Fields in the order given, each exact, then prefix, then contains: a hit in
        # the first field outranks any hit in a later one.
        rank = case(
            *(
                (condition, i)
                for i, condition in enumerate(
                    condition
                    for c in columns
                    for condition in (
                        func.lower(c) == q.lower(),
                        c.istartswith(q, autoescape=True),
                        c.icontains(q, autoescape=True),
                    )
                )
            ),
            else_=len(columns) * 3,
        )
        selected = [
            self.model.id.label("id"),
            self.label.label("label"),
            *(c.label(f"sub_{i}") for i, c in enumerate(self.sublabel)),
            *(c.label(f"field_{name}") for name, c in self.fields.items()),
        ]
        statement = self.statement(*selected).where(match).order_by(rank, func.lower(self.label), self.model.id)
        rows = session.execute(statement.limit(limit)).mappings().all()
        return SearchGroup(type=self.type, total=total, items=[self.hit(row, q) for row in rows])

    def statement(self, *columns):
        statement = select(*columns).select_from(self.model)
        for target, on in self.joins:
            statement = statement.outerjoin(target, on)
        return statement

    def hit(self, row, q: str) -> SearchHit:
        values = {name: row[f"field_{name}"] for name in self.fields}
        # The database decided the row matches; this only names the field. Where its
        # case folding differs from Python's (SQLite outside ASCII), fall back to the first.
        field = next((n for n, v in values.items() if v and q.casefold() in str(v).casefold()), next(iter(values)))
        sublabel = [str(row[f"sub_{i}"]) for i in range(len(self.sublabel)) if row[f"sub_{i}"]]
        return SearchHit(
            id=row["id"],
            label=row["label"] or "",
            sublabel=" · ".join(sublabel) or None,
            matched_field=field,
            matched_value=str(values[field] or ""),
        )


class SearchService:
    """Finds inventory objects of every kind whose identifying fields contain a search text."""

    MIN_LENGTH = 2

    def __init__(self, db_manager):
        self.db = db_manager

    async def search(self, q: str, limit: int = 5) -> SearchResponse:
        q = q.strip()
        if len(q) < self.MIN_LENGTH:
            return SearchResponse(query=q, groups=[])
        session = next(self.db.get_session())
        try:
            groups = [target.search(session, q, limit) for target in self.targets(q)]
        finally:
            session.close()
        return SearchResponse(query=q, groups=[g for g in groups if g.total])

    def targets(self, q: str) -> list[SearchTarget]:
        # A node can have several management connections; this is the first one that matches, if any.
        management_ip = (
            select(func.min(ManagementConnection.target_ip))
            .where(ManagementConnection.node_id == Node.id)
            .where(ManagementConnection.target_ip.icontains(q, autoescape=True))
            .scalar_subquery()
        )
        return [
            SearchTarget(
                SearchHitType.logical_node,
                LogicalNode,
                label=LogicalNode.hostname,
                fields={"hostname": LogicalNode.hostname, "site": LogicalNode.site, "role": LogicalNode.role},
                sublabel=(LogicalNode.site, LogicalNode.role),
            ),
            SearchTarget(
                SearchHitType.node_instance,
                Node,
                label=LogicalNode.hostname,
                fields={
                    "hostname": LogicalNode.hostname,
                    "management_ip": management_ip,
                    "serial_number": Asset.serial_number,
                },
                sublabel=(LogicalNode.site, Asset.serial_number),
                joins=(
                    (LogicalNode, LogicalNode.id == Node.logical_node_id),
                    (Asset, (Node.asset_ref_type == AssetRefType.asset) & (Asset.id == Node.asset_ref_id)),
                ),
            ),
            SearchTarget(
                SearchHitType.site,
                Site,
                label=Site.name,
                fields={
                    "name": Site.name,
                    "display_name": Site.display_name,
                    "city": Site.city,
                    "country": Site.country,
                    "address": Site.address,
                },
                sublabel=(Site.display_name, Site.city, Site.country),
            ),
            SearchTarget(
                SearchHitType.region,
                Region,
                label=Region.name,
                fields={"name": Region.name, "display_name": Region.display_name},
                sublabel=(Region.display_name,),
            ),
            SearchTarget(
                SearchHitType.asset,
                Asset,
                label=Asset.serial_number,
                fields={"serial_number": Asset.serial_number, "hardware_model": Asset.hardware_model},
                sublabel=(Asset.vendor, Asset.hardware_model),
            ),
            SearchTarget(
                SearchHitType.asset_cluster,
                AssetCluster,
                label=AssetCluster.name,
                fields={"name": AssetCluster.name},
            ),
            SearchTarget(
                SearchHitType.contact,
                Contact,
                label=func.coalesce(Contact.display_name, Contact.name),
                fields={
                    "name": Contact.name,
                    "display_name": Contact.display_name,
                    "email": Contact.email,
                    "phone": Contact.phone,
                },
                sublabel=(Contact.role, Contact.email),
            ),
        ]
