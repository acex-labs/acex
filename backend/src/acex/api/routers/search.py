from acex.constants import BASE_URL
from acex.search import SearchService
from acex_devkit.models.search import SearchResponse
from fastapi import APIRouter


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/search")
    tags = ["Search"]

    search = SearchService(automation_engine.db)

    router.add_api_route("", search.search, methods=["GET"], response_model=SearchResponse, tags=tags)

    return router
