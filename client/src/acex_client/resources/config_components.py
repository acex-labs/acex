from acex_devkit.models.config_components import (
    ConfigComponentCatalogEntry,
    ConfigMapGenerateRequest,
    ConfigMapGenerateResponse,
    NedDriverEntry,
    ReconcileRequest,
    ReconcileResponse,
    TranslateRequest,
    TranslateResponse,
)

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)


class ConfigComponents(Resource, ActionMixin):
    """Component catalog and ConfigMap generation — `/config_components/*`."""

    path = "/config_components"
    response_model = None  # type: ignore
    list_model = None  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "")
    def catalog(self) -> list[ConfigComponentCatalogEntry]: ...

    @action("POST", "generate")
    def generate(self, payload: ConfigMapGenerateRequest) -> ConfigMapGenerateResponse: ...

    @action("POST", "reconcile/{node_instance_id}")
    def reconcile(
        self,
        node_instance_id: int,
        payload: ReconcileRequest | None = None,
    ) -> ReconcileResponse: ...

    @action("GET", "drivers")
    def drivers(self) -> list[NedDriverEntry]: ...

    @action("POST", "translate")
    def translate(self, payload: TranslateRequest) -> TranslateResponse: ...
