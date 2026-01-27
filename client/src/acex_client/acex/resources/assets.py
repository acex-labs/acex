
from acex_client.models.models import AssetResponse
from .resource_base import Resource


class Assets(Resource):

    ENDPOINT =  "/inventory/assets/"
    RESPONSE_MODEL = AssetResponse

