from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.models.onboarding import OnboardingReport, OnboardingRequest
from app.services.onboarding_service import OnboardingService

router = APIRouter()
_service: OnboardingService | None = None


def get_service() -> OnboardingService:
    global _service
    if _service is None:
        _service = OnboardingService()
    return _service


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/onboardings", response_model=OnboardingReport, status_code=201)
def create_onboarding(req: OnboardingRequest, svc: OnboardingService = Depends(get_service)):
    return svc.create(req)


@router.get("/onboardings", response_model=List[OnboardingReport])
def list_onboardings(svc: OnboardingService = Depends(get_service)):
    return svc.list()


@router.get("/onboardings/{report_id}", response_model=OnboardingReport)
def get_onboarding(report_id: str, svc: OnboardingService = Depends(get_service)):
    report = svc.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
