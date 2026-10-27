import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agents.architecture_agent import ArchitectureAnalysisAgent
from app.api.discovery_routes import resolve_root
from app.core.config import get_settings
from app.models.architecture import ArchitectureResult
from app.models.discovery import DiscoveryRequest

router = APIRouter(prefix="/architecture", tags=["architecture"])


@router.post("", response_model=ArchitectureResult, response_model_by_alias=True)
def analyze_architecture(body: DiscoveryRequest):
    root = resolve_root(body)
    try:
        result = ArchitectureAnalysisAgent().run(root)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Architecture analysis failed: {exc}")
    out_dir = Path(get_settings().reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"architecture-{result.applicationName}.json").write_text(
        json.dumps(result.model_dump(by_alias=True), indent=2), encoding="utf-8")
    return result
