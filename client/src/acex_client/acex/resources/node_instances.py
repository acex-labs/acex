from acex_devkit.models import NodeListItem, NodeResponse

from .resource_base import CreateMixin, DeleteMixin, GetMixin, ListMixin, Resource, UpdateMixin


class NodeInstances(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin):
    ENDPOINT = "/inventory/node_instances/"
    RESPONSE_MODEL_SINGLE = NodeResponse
    RESPONSE_MODEL_LIST = NodeListItem
