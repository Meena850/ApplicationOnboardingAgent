import json
import logging
import re
from typing import Any, Dict, List, Set

from pydantic import ValidationError

from app.core.config import get_settings
from app.models.architecture import ArchitectureResult
from app.models.features import FeatureUnderstandingResult
from app.services.llm_service import AzureOpenAIService, LLMError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior software analyst. You are given deterministic analysis data of an \
application's source code (modules, routes, API endpoints, dependencies). Infer what the application does \
for its users.

Rules:
- Use ONLY the provided data. Never invent modules, routes or files.
- In every "modules" / "components" list, use exact names that appear in the data (module names, controller, \
service, repository, page, component, view or layout names).
- "reasoning" must cite concrete evidence from the data (route paths, controller/page names, packages).
- "confidence" is an integer 0-100 reflecting how strongly the evidence supports the item. Be conservative: \
thin or purely structural evidence must score below 60.
- If the data is too thin to infer something, return fewer items instead of guessing.

Return a single JSON object with exactly these keys:
{
  "summary": "2-3 sentence description of what the application does",
  "businessCapabilities": [{"name": "", "description": "", "modules": [], "reasoning": "", "confidence": 0}],
  "features": [{"name": "", "summary": "", "modules": [], "reasoning": "", "confidence": 0}],
  "userWorkflows": [{"name": "", "steps": [], "features": [], "reasoning": "", "confidence": 0}],
  "functionalModules": [{"name": "", "purpose": "", "components": [], "features": [], "confidence": 0}],
  "overallConfidence": 0
}"""


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


class FeatureUnderstandingAgent:
    """Uses Azure OpenAI to describe business capabilities, features, workflows and functional modules
    from analyzed repository data (ArchitectureResult). Output names are grounded against that data."""

    def __init__(self, llm: AzureOpenAIService | None = None) -> None:
        self._llm = llm
        self.max_chars = get_settings().azure_openai_max_context_chars

    @property
    def llm(self) -> AzureOpenAIService:
        if self._llm is None:
            self._llm = AzureOpenAIService()
        return self._llm

    # ---- context -------------------------------------------------
    def build_context(self, arch: ArchitectureResult) -> tuple[str, List[str]]:
        warnings: List[str] = []
        ctx: Dict[str, Any] = {
            "applicationName": arch.applicationName,
            "modules": [{"name": n.name, "type": n.type, "layers": n.layers}
                        for n in arch.moduleMap.nodes],
            "moduleEdges": [e.model_dump(by_alias=True) for e in arch.moduleMap.edges],
            "routes": [{"path": r.path, "method": r.method, "handler": r.handler, "view": r.view}
                       for r in arch.routeMap.routes],
            "apiEndpoints": [f"{e.method} {e.route} ({e.controller or ''}.{e.action or ''})"
                             for e in arch.apiMap.endpoints],
            "clientCalls": [f"{c.method} {c.route}" for c in arch.apiMap.clientCalls],
            "packages": [f"{p.name}@{p.version or ''}" for p in arch.dependencyMap.packages],
            "serviceRegistrations": [f"{r.service}->{r.implementation}" for r in arch.dependencyMap.registrations],
            "internalDependencies": [f"{e.source}->{e.target}" for e in arch.dependencyMap.internal],
        }
        text = json.dumps(ctx, separators=(",", ":"))
        # Trim the least informative, largest lists first until the context fits.
        for key in ("internalDependencies", "packages", "clientCalls", "apiEndpoints", "routes"):
            while len(text) > self.max_chars and ctx[key]:
                ctx[key] = ctx[key][: max(0, len(ctx[key]) // 2)]
                text = json.dumps(ctx, separators=(",", ":"))
                if key not in " ".join(warnings):
                    warnings.append(f"Context truncated: '{key}' was shortened to fit the model limit.")
        return text, warnings

    @staticmethod
    def known_names(arch: ArchitectureResult) -> Set[str]:
        names: Set[str] = set()

        def add(s: str | None) -> None:
            if not s:
                return
            names.add(_key(s))
            for part in re.split(r"[/.\\]", s):
                if part:
                    names.add(_key(part))
                    if part.endswith("Controller"):
                        names.add(_key(part[: -len("Controller")]))

        for n in arch.moduleMap.nodes:
            add(n.name)
            for items in n.layers.values():
                for it in items:
                    add(it)
        for r in arch.routeMap.routes:
            add(r.handler)
            add(r.view)
        for e in arch.apiMap.endpoints:
            add(e.controller)
        for reg in arch.dependencyMap.registrations:
            add(reg.service)
            add(reg.implementation)
        return names

    # ---- run -----------------------------------------------------
    def run(self, arch: ArchitectureResult) -> FeatureUnderstandingResult:
        warnings: List[str] = []
        if not (arch.routeMap.routes or arch.apiMap.endpoints or arch.moduleMap.nodes):
            raise LLMError("No analyzable modules, routes or endpoints were found in this repository.")

        context, ctx_warnings = self.build_context(arch)
        warnings += ctx_warnings
        raw = self.llm.complete_json(SYSTEM_PROMPT, f"Analyzed repository data (JSON):\n{context}")
        raw["applicationName"] = arch.applicationName
        try:
            result = FeatureUnderstandingResult.model_validate(raw)
        except ValidationError as exc:
            logger.warning("Invalid model output: %s", exc)
            raise LLMError("Model output did not match the expected structure.") from exc

        known = self.known_names(arch)
        dropped = self._ground(result, known)
        if dropped:
            warnings.append("Removed names not found in the analyzed data: " + ", ".join(sorted(dropped)))
        if not (arch.routeMap.routes or arch.apiMap.endpoints):
            result.overallConfidence = min(result.overallConfidence, 30)
            warnings.append("No routes or API endpoints were found; confidence capped at 30%.")
        result.model = self.llm.deployment
        result.warnings = warnings
        logger.info("Feature understanding of %s: %d features, confidence %d%%",
                    result.applicationName, len(result.features), result.overallConfidence)
        return result

    @staticmethod
    def _ground(result: FeatureUnderstandingResult, known: Set[str]) -> Set[str]:
        dropped: Set[str] = set()

        def keep(names: List[str]) -> List[str]:
            out = []
            for n in names:
                if _key(n) in known:
                    out.append(n)
                else:
                    dropped.add(n)
            return out

        for cap in result.businessCapabilities:
            cap.modules = keep(cap.modules)
        for feat in result.features:
            feat.modules = keep(feat.modules)
        for fm in result.functionalModules:
            fm.components = keep(fm.components)
        return dropped
