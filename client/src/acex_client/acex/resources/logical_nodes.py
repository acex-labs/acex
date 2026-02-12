
from acex_client.models.generated_models import LogicalNode,LogicalNodeResponse
from .resource_base import Resource


class LogicalNodes(Resource):

    ENDPOINT =  "/inventory/logical_nodes/"
    RESPONSE_MODEL_SINGLE = LogicalNodeResponse
    RESPONSE_MODEL_LIST = LogicalNode
