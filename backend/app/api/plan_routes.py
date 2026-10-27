import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agents.planning_agent import ImplementationPlanningAgent
from app.api.discovery_routes import resolve_root
from app.core.config import get_settings
from app.models.plan import ImplementationPlan, ImpactRequest

router = APIRouter(prefix="/plan", tags=["plan"])


@router.post("", response_model=ImplementationPlan, response_model_by_alias=True)
def create_plan(body: ImpactRequest):
    base_root, enh_root = resolve_root(body.base), resolve_root(body.enhancement)
    try:
        plan = ImplementationPlanningAgent().analyze_and_plan(base_root, enh_root, top_n=body.topN)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Planning failed: {exc}")
    out_dir = Path(get_settings().reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"plan-{plan.baseApplication}-vs-{plan.enhancementApplication}"
    (out_dir / f"{stem}.json").write_text(json.dumps(plan.model_dump(by_alias=True), indent=2), encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(plan.planMarkdown, encoding="utf-8")
    return plan
