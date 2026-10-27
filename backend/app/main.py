import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.architecture_routes import router as architecture_router
from app.api.comparison_routes import router as comparison_router
from app.api.diagram_routes import router as diagram_router
from app.api.discovery_routes import router as discovery_router
from app.api.feature_routes import router as feature_router
from app.api.impact_routes import router as impact_router
from app.api.plan_routes import router as plan_router
from app.api.recommendation_routes import router as recommendation_router
from app.api.repository_routes import router as repository_router
from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")
app.include_router(repository_router, prefix="/api")
app.include_router(discovery_router, prefix="/api")
app.include_router(architecture_router, prefix="/api")
app.include_router(comparison_router, prefix="/api")
app.include_router(feature_router, prefix="/api")
app.include_router(impact_router, prefix="/api")
app.include_router(plan_router, prefix="/api")
app.include_router(diagram_router, prefix="/api")
app.include_router(recommendation_router, prefix="/api")
logger.info("%s started (%s)", settings.app_name, settings.environment)
