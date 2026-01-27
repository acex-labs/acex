
from acex_client.models.models import LogicalNode, Ned
from .resource_base import Resource


class LogicalNodes(Resource):

    ENDPOINT =  "/inventory/logical_nodes/"
    RESPONSE_MODEL = LogicalNode
