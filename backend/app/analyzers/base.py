from abc import ABC, abstractmethod
from typing import List

from app.models.onboarding import Finding, OnboardingRequest


class BaseAnalyzer(ABC):
    """Inspects an application (repo, config, deps) and returns findings."""

    @abstractmethod
    def analyze(self, request: OnboardingRequest) -> List[Finding]: ...


class BasicAnalyzer(BaseAnalyzer):
    def analyze(self, request: OnboardingRequest) -> List[Finding]:
        findings = [Finding(category="general", message=f"Analyzed '{request.name}'.")]
        if not request.repo_url:
            findings.append(Finding(category="source", message="No repository URL provided."))
        return findings
