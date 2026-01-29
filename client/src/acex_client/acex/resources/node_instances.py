
from acex_client.models.models import Node, NodeResponse, Ned
from .resource_base import Resource


class NodeInstances(Resource):

    ENDPOINT =  "/inventory/node_instances/"
    RESPONSE_MODEL_SINGLE = NodeResponse
    RESPONSE_MODEL_LIST = Node

