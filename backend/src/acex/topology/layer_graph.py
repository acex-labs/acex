from acex_devkit.models.topology import TopologyLink, TopologyNode

NODE_INSTANCE_PREFIX = "node:"


class LayerGraph:
    """The links one layer found, and the nodes it brought that are not node instances.

    Node instances are referred to by id only; the service describes them once for all layers. A link seen
    from both ends is kept once: its id is the layer and its two endpoints in a fixed order.
    """

    def __init__(self):
        self.nodes: dict[str, TopologyNode] = {}
        self.links: dict[str, TopologyLink] = {}

    @staticmethod
    def node_instance_id(node_instance_id: int) -> str:
        return f"{NODE_INSTANCE_PREFIX}{node_instance_id}"

    def add_node(self, node: TopologyNode):
        self.nodes.setdefault(node.id, node)

    def add_link(self, link: TopologyLink):
        sides = sorted(f"{end.node}#{end.interface}" for end in (link.a, link.b))
        link_id = f"{link.layer}|{sides[0]}|{sides[1]}"
        if link_id not in self.links:
            self.links[link_id] = link.model_copy(update={"id": link_id})

    def node_instance_ids(self) -> set[int]:
        ids = set()
        for link in self.links.values():
            for end in (link.a, link.b):
                if end.node.startswith(NODE_INSTANCE_PREFIX):
                    ids.add(int(end.node.removeprefix(NODE_INSTANCE_PREFIX)))
        return ids
