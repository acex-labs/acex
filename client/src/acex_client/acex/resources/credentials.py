
from acex_devkit.models.credential import CredentialResponse
from .resource_base import Resource


class Credential(Resource):

    ENDPOINT = "/inventory/credentials/"
    RESPONSE_MODEL_SINGLE = CredentialResponse
    RESPONSE_MODEL_LIST = CredentialResponse

