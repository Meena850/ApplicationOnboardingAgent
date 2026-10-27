from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class OnboardingRequest(BaseModel):
    name: str = Field(..., min_length=1)
    repo_url: Optional[str] = None
    description: Optional[str] = None


class Finding(BaseModel):
    category: str
    message: str


class OnboardingReport(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    findings: List[Finding] = []
