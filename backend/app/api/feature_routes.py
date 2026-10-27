import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agents.architecture_agent import ArchitectureAnalysisAgent
from app.agents.feature_agent import FeatureUnderstandingAgent
from app.api.discovery_routes import resolve_root
from app.core.config import get_settings
from app.models.discovery import DiscoveryRequest
from app.models.features import FeatureUnderstandingResult
from app.services.llm_service import LLMError, LLMNotConfiguredError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/features", tags=["features"])


@router.post("", response_model=FeatureUnderstandingResult, response_model_by_alias=True)
def understand_features(body: DiscoveryRequest):
    root = resolve_root(body)
    architecture = ArchitectureAnalysisAgent().run(root)
    try:
        result = FeatureUnderstandingAgent().run(architecture)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    out_dir = Path(get_settings().reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"features-{result.applicationName}.json").write_text(
        json.dumps(result.model_dump(by_alias=True), indent=2), encoding="utf-8")
    return result
