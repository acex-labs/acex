
from acex_client.models.generated_models import Node, Ned
from acex_devkit.models import NodeResponse
from .resource_base import Resource

class NodeInstances(Resource):

    ENDPOINT =  "/inventory/node_instances/"
    RESPONSE_MODEL_SINGLE = NodeResponse
    RESPONSE_MODEL_LIST = Node

