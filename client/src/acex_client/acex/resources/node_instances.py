from acex_devkit.models import NodeResponse, NodeListItem
from .resource_base import Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin


class NodeInstances(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin):

    ENDPOINT = "/inventory/node_instances/"
    RESPONSE_MODEL_SINGLE = NodeResponse
    RESPONSE_MODEL_LIST = NodeListItem
