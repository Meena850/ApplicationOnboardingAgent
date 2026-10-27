from typing import List

from fastapi import APIRouter, HTTPException

from app.models.repository import (
    AnalysisRecord,
    AnalyzeRequest,
    RepositoryInput,
    RepositoryMetadata,
)
from app.services.repository_service import RepositoryError, RepositoryService

router = APIRouter(prefix="/repositories", tags=["repositories"])
_service: RepositoryService | None = None


def get_service() -> RepositoryService:
    global _service
    if _service is None:
        _service = RepositoryService()
    return _service


def _http(exc: RepositoryError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/ingest", response_model=RepositoryMetadata, status_code=201)
def ingest(body: RepositoryInput):
    try:
        return get_service().ingest(body)
    except RepositoryError as exc:
        raise _http(exc)


@router.post("/analyze", response_model=AnalysisRecord, status_code=201)
def analyze(body: AnalyzeRequest):
    try:
        return get_service().analyze(body)
    except RepositoryError as exc:
        raise _http(exc)


@router.get("", response_model=List[RepositoryMetadata])
def list_repositories():
    return get_service().list()


@router.get("/{repo_id}", response_model=RepositoryMetadata)
def get_repository(repo_id: str):
    try:
        return get_service().get(repo_id)
    except RepositoryError as exc:
        raise _http(exc)
