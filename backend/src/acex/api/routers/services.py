from acex.constants import BASE_URL
from fastapi import APIRouter


def create_router(automation_engine):
    router = APIRouter(prefix=BASE_URL, tags=["Auth"])

    @router.get("/services")
    def get_services() -> dict[str, dict[str, str]]:
        """Other backends the frontend calls directly, keyed by service: `{"samruai": {"url": ...}}`.

        Only configured services are listed (ACEX_SERVICES_<SERVICE>_URL); see ServicesSettings.
        """
        return automation_engine.settings.services.public()

    return router
