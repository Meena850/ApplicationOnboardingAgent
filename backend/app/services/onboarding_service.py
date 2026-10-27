import logging
import uuid
from pathlib import Path
from typing import List, Optional

from app.agents.base import OnboardingAgent
from app.core.config import get_settings
from app.models.onboarding import OnboardingReport, OnboardingRequest

logger = logging.getLogger(__name__)


class OnboardingService:
    def __init__(self) -> None:
        self.agent = OnboardingAgent()
        self.reports_dir = Path(get_settings().reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def create(self, request: OnboardingRequest) -> OnboardingReport:
        report = self.agent.run(request, uuid.uuid4().hex)
        (self.reports_dir / f"{report.id}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Report %s saved", report.id)
        return report

    def get(self, report_id: str) -> Optional[OnboardingReport]:
        path = self.reports_dir / f"{Path(report_id).name}.json"
        if not path.exists():
            return None
        return OnboardingReport.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> List[OnboardingReport]:
        # reports/ also holds architecture/plan/diagram output from other agents;
        # only files that are onboarding reports are returned.
        reports: List[OnboardingReport] = []
        for p in sorted(self.reports_dir.glob("*.json")):
            try:
                reports.append(OnboardingReport.model_validate_json(p.read_text(encoding="utf-8")))
            except ValueError:
                continue
        return reports
