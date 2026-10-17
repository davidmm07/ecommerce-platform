from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ecommerce.presentation.api.dependencies import ContainerDep

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe", responses={503: {"description": "Not ready"}})
async def ready(container: ContainerDep) -> JSONResponse:
    if await container.database_is_ready():
        return JSONResponse({"status": "ok", "database": "up"})
    return JSONResponse({"status": "unavailable", "database": "down"}, status_code=503)
