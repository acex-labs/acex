
from acex_client.models.generated_models import AssetResponse
from .resource_base import Resource


class Assets(Resource):

    ENDPOINT =  "/inventory/assets/"
    RESPONSE_MODEL_SINGLE = AssetResponse
    RESPONSE_MODEL_LIST = AssetResponse
