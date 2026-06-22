from acex_devkit.models.credential import CredentialResponse
from .resource_base import Resource, GetMixin, ListMixin, CreateMixin


class Credential(Resource, GetMixin, ListMixin, CreateMixin):

    ENDPOINT = "/inventory/credentials/"
    RESPONSE_MODEL_SINGLE = CredentialResponse
    RESPONSE_MODEL_LIST = CredentialResponse
