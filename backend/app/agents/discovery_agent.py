import json
import logging
from pathlib import Path
from typing import List, Optional

from app.analyzers.discovery import (
    DotNetAnalyzer, ProjectAnalyzer, RazorAnalyzer, ReactAnalyzer, SourceAnalyzer,
)
from app.models.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


class SourceCodeDiscoveryAgent:
    """Scans a repository (React, .NET, Razor) and returns a structured inventory."""

    def __init__(self, analyzers: Optional[List[SourceAnalyzer]] = None) -> None:
        self.analyzers = analyzers or [ProjectAnalyzer(), ReactAnalyzer(), DotNetAnalyzer(), RazorAnalyzer()]

    def run(self, root: Path) -> DiscoveryResult:
        root = root.resolve()
        result = DiscoveryResult(applicationName=root.name)
        for analyzer in self.analyzers:
            try:
                analyzer.analyze(root, result)
            except Exception as exc:  # noqa: BLE001 - one analyzer must not kill the scan
                logger.exception("%s failed", type(analyzer).__name__)
                result.warnings.append(f"{type(analyzer).__name__} failed: {exc}")
        result.applicationName = self._application_name(root, result)
        self._dedupe(result)
        logger.info("Discovery of %s: %d routes, %d apis, %d controllers",
                    result.applicationName, len(result.routes), len(result.apis), len(result.controllers))
        return result

    @staticmethod
    def _application_name(root: Path, result: DiscoveryResult) -> str:
        top = sorted(result.modules, key=lambda m: len(Path(m.path).parts))
        for m in top:
            if m.type in ("dotnet", "react"):
                return m.name
        return root.name

    @staticmethod
    def _dedupe(result: DiscoveryResult) -> None:
        for field in ("routes", "apis", "dependencies", "pages", "services", "components", "hooks"):
            seen, out = set(), []
            for item in getattr(result, field):
                key = json.dumps(item.model_dump(), sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    out.append(item)
            setattr(result, field, out)
