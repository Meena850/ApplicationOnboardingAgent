import logging
from pathlib import Path

from app.agents.discovery_agent import SourceCodeDiscoveryAgent
from app.analyzers.architecture import (
    ModuleIndex, build_api_map, build_dependency_map, build_module_map, build_route_map,
)
from app.models.architecture import ArchitectureResult
from app.models.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


class ArchitectureAnalysisAgent:
    """Builds module, route, API and dependency maps from a repository path.

    Deterministic: reuses the discovery inventory and parses code; no AI involved.
    """

    def __init__(self, discovery: SourceCodeDiscoveryAgent | None = None) -> None:
        self.discovery = discovery or SourceCodeDiscoveryAgent()

    def run(self, root: Path) -> ArchitectureResult:
        root = root.resolve()
        return self.from_discovery(root, self.discovery.run(root))

    def from_discovery(self, root: Path, d: DiscoveryResult) -> ArchitectureResult:
        """Build the maps from an already computed discovery result (avoids a second scan)."""
        root = root.resolve()
        idx = ModuleIndex(d.modules)
        warnings = list(d.warnings)

        def safe(label, fn, default):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - keep other maps usable
                logger.exception("%s failed", label)
                warnings.append(f"{label} failed: {exc}")
                return default

        from app.models.architecture import ApiMap, DependencyMap, ModuleMap, RouteMap

        api_map = safe("apiMap", lambda: build_api_map(d, idx), ApiMap())
        route_map = safe("routeMap", lambda: build_route_map(d, idx), RouteMap())
        module_map = safe("moduleMap", lambda: build_module_map(root, d, idx, api_map), ModuleMap())
        dep_map = safe("dependencyMap", lambda: build_dependency_map(root, d, idx), DependencyMap())

        result = ArchitectureResult(
            applicationName=d.applicationName,
            repositoryPath=str(root),
            moduleMap=module_map, routeMap=route_map, apiMap=api_map, dependencyMap=dep_map,
            summary={
                "modules": len(module_map.nodes),
                "routes": len(route_map.routes),
                "apiEndpoints": len(api_map.endpoints),
                "apiClientCalls": len(api_map.clientCalls),
                "packages": len(dep_map.packages),
                "internalDependencies": len(dep_map.internal),
            },
            warnings=warnings,
        )
        logger.info("Architecture of %s: %s", result.applicationName, result.summary)
        return result
