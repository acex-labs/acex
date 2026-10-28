from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.cve.cve_manager import CveManager
from acex.jobs import JobPublishError
from acex.messaging import MessagingNotConfigured
from acex_devkit.models.credential import CredentialCreate, CredentialResponse, CredentialUpdate
from acex_devkit.models.cve import CveApiKeyUpdate, CveCreate, CveDiscoverData, CveResponse, CveUpdate
from acex_devkit.models.job import JobResponse
from acex_devkit.models.pagination import PaginatedResponse
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError

_NVD_CREDENTIAL_NAME = "acex.cve.nvd"


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/cves", tags=["CVE"])
    cves: CveManager = automation_engine.cves

    def nvd_credential() -> CredentialResponse | None:
        credentials = automation_engine.credential_manager.query(name=_NVD_CREDENTIAL_NAME)
        credential = next((item for item in credentials if item.name == _NVD_CREDENTIAL_NAME), None)
        if credential is not None and (credential.credential_type != "token" or credential.source != "local"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Credential {_NVD_CREDENTIAL_NAME} must be a local token credential",
            )
        return credential

    @router.get("/api_key", response_model=str | None, dependencies=[Depends(_auth.get_current_user)])
    def api_key(response: Response) -> str | None:
        response.headers["Cache-Control"] = "no-store"
        credential = nvd_credential()
        if credential is None:
            return None
        secret = automation_engine.credential_manager.get_secret(credential.id)
        if not secret.fields.get("token"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NVD credential has no token; replace it using PUT /cves/api_key",
            )
        return secret.fields["token"]

    @router.put("/api_key", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_auth.get_current_user)])
    def set_api_key(payload: CveApiKeyUpdate) -> Response:
        credential = nvd_credential()
        cm = automation_engine.credential_manager
        try:
            if credential is None:
                cm.create(
                    CredentialCreate(
                        name=_NVD_CREDENTIAL_NAME,
                        credential_type="token",
                        fields={"token": payload.api_key},
                    )
                )
            else:
                cm.update(credential.id, CredentialUpdate(fields={"token": payload.api_key}))
        except IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NVD credential was changed concurrently; retry the request",
            ) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})

    @router.delete("/api_key", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_auth.get_current_user)])
    def delete_api_key() -> Response:
        credential = nvd_credential()
        if credential is not None:
            automation_engine.credential_manager.delete(credential.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})

    @router.post("/discover", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def discover(
        payload: CveDiscoverData,
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        try:
            return automation_engine.jobs.enqueue(
                "acex.cve.discover",
                payload,
                created_by=user.get("sub") or "anonymous",
            )
        except MessagingNotConfigured as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        except JobPublishError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    @router.post("/bulk", response_model=list[CveResponse])
    def bulk_create(payload: list[CveCreate]):
        return cves.bulk_create(payload)

    @router.get("/{cve_id}", response_model=CveResponse)
    def get(cve_id: int):
        cve = cves.get(cve_id)
        if cve is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No CVE {cve_id}")
        return cve

    @router.get("", response_model=PaginatedResponse[CveResponse])
    def query(limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0)):
        return cves.query(limit=limit, offset=offset)

    @router.post("", response_model=CveResponse, status_code=status.HTTP_201_CREATED)
    def create(payload: CveCreate):
        try:
            return cves.create(payload)
        except IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"CVE {payload.cve_id} already exists",
            ) from exc

    @router.patch("/{cve_id}", response_model=CveResponse)
    def update(cve_id: int, payload: CveUpdate):
        try:
            cve = cves.update(cve_id, payload)
        except IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"CVE {cve_id} already exists",
            ) from exc
        if cve is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No CVE {cve_id}")
        return cve

    return router
