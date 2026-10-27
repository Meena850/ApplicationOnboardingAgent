import logging
from abc import ABC, abstractmethod

from app.analyzers.base import BaseAnalyzer, BasicAnalyzer
from app.models.onboarding import OnboardingReport, OnboardingRequest

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    @abstractmethod
    def run(self, request: OnboardingRequest, report_id: str) -> OnboardingReport: ...


class OnboardingAgent(BaseAgent):
    """Placeholder agent; plug in an LLM / tool-calling loop here."""

    def __init__(self, analyzer: BaseAnalyzer | None = None):
        self.analyzer = analyzer or BasicAnalyzer()

    def run(self, request: OnboardingRequest, report_id: str) -> OnboardingReport:
        logger.info("Agent running for %s", request.name)
        findings = self.analyzer.analyze(request)
        return OnboardingReport(id=report_id, name=request.name, status="completed", findings=findings)
