import json
from importlib.metadata import version
from importlib.resources import files

from acex.constants import BASE_URL
from fastapi import APIRouter
from pydantic import BaseModel


class ChangelogEntry(BaseModel):
    title: str
    description: str | None = None
    group: str
    breaking: bool = False
    pr: int | None = None
    commit: str
    pr_url: str | None = None
    commit_url: str | None = None


class ChangelogRelease(BaseModel):
    version: str
    date: str | None = None
    entries: list[ChangelogEntry]


class ChangelogResponse(BaseModel):
    version: str
    releases: list[ChangelogRelease]


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/changelog")
    tags = ["Changelog"]

    def changelog() -> ChangelogResponse:
        releases: list[ChangelogRelease] = []
        try:
            raw = files("acex").joinpath("changelog.json").read_text(encoding="utf-8")
            releases = [ChangelogRelease.model_validate(r) for r in json.loads(raw)["releases"]]
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            pass
        return ChangelogResponse(version=version("acex"), releases=releases)

    router.add_api_route("", changelog, methods=["GET"], tags=tags, response_model=ChangelogResponse)

    return router