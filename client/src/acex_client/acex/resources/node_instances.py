
from acex_devkit.models import NodeResponse, NodeListItem
from .resource_base import Resource


class NodeInstances(Resource):

    ENDPOINT = "/inventory/node_instances/"
    RESPONSE_MODEL_SINGLE = NodeResponse
    RESPONSE_MODEL_LIST = NodeListItem

