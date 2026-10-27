import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agents.discovery_agent import SourceCodeDiscoveryAgent
from app.core.config import get_settings
from app.models.discovery import DiscoveryRequest, DiscoveryResult
from app.services.repository_service import RepositoryError, RepositoryService

router = APIRouter(prefix="/discovery", tags=["discovery"])


def resolve_root(body: DiscoveryRequest) -> Path:
    """Resolve the repository directory from a repositoryId or a local path."""
    if body.repositoryId:
        try:
            root = Path(RepositoryService().get(body.repositoryId).local_path)
        except RepositoryError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message)
    elif body.path:
        root = Path(body.path)
    else:
        raise HTTPException(status_code=400, detail="Provide 'path' or 'repositoryId'.")
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory not found: {root}")
    return root


@router.post("", response_model=DiscoveryResult, response_model_by_alias=True)
def discover(body: DiscoveryRequest):
    result = SourceCodeDiscoveryAgent().run(resolve_root(body))
    out_dir = Path(get_settings().reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"discovery-{result.applicationName}.json").write_text(
        json.dumps(result.model_dump(by_alias=True), indent=2), encoding="utf-8")
    return result
