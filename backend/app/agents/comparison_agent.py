import logging
import re
from pathlib import Path
from typing import Dict, List, Set

from app.agents.architecture_agent import ArchitectureAnalysisAgent
from app.agents.discovery_agent import SourceCodeDiscoveryAgent
from app.analyzers.entities import extract_entities
from app.models.comparison import (
    CategoryComparison, ComparisonResult, ComponentRef, IntegrationCandidate,
    MissingComponent, ModifiedComponent, RepositorySnapshot,
)

logger = logging.getLogger(__name__)

# Integration order: data first, then logic, then the surface that exposes it.
KIND_ORDER = ["module", "entity", "service", "api", "route"]
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _k(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _route_key(path: str, method: str | None) -> str:
    p = re.sub(r"\{[^}]*\}", "{}", path.lower())
    return f"{(method or 'GET').upper()} /{p.strip('/')}"


class Item:
    """A comparable component. `scalars` conflict when they differ; `sets` only ever add."""

    def __init__(self, kind: str, name: str, file: str | None = None,
                 scalars: Dict[str, str] | None = None, sets: Dict[str, Set[str]] | None = None,
                 details: Dict[str, str] | None = None) -> None:
        self.kind, self.name, self.file = kind, name, file
        self.scalars, self.sets, self.details = scalars or {}, sets or {}, details or {}

    def ref(self) -> ComponentRef:
        return ComponentRef(kind=self.kind, name=self.name, file=self.file, details=self.details)


class RepositoryComparisonAgent:
    """Compares a base and an enhancement application analysis. Deterministic, no AI."""

    # ---- analysis ---------------------------------------------------
    def analyze(self, root: Path) -> RepositorySnapshot:
        root = root.resolve()
        discovery = SourceCodeDiscoveryAgent().run(root)
        architecture = ArchitectureAnalysisAgent().from_discovery(root, discovery)
        return RepositorySnapshot(discovery=discovery, architecture=architecture,
                                  entities=extract_entities(root))

    # ---- item extraction -------------------------------------------
    @staticmethod
    def _deps(snap: RepositorySnapshot, name: str, file: str | None) -> Set[str]:
        return {e.target for e in snap.architecture.dependencyMap.internal
                if e.source == name or (file is not None and e.source == file)}

    def items(self, snap: RepositorySnapshot) -> Dict[str, Dict[str, Item]]:
        arch, out = snap.architecture, {k: {} for k in KIND_ORDER}
        for n in arch.moduleMap.nodes:
            out["module"][_k(n.name)] = Item(
                "module", n.name, n.path, details={"type": n.type},
                sets={layer: set(v) for layer, v in n.layers.items()})
        for r in arch.routeMap.routes:
            sc = {"handler": r.handler} if r.handler else {}
            out["route"][_route_key(r.path, r.method)] = Item(
                "route", f"{(r.method or 'GET').upper()} {r.path}", r.file, scalars=sc,
                details={"handler": r.handler or "", "source": r.source})
        for e in arch.apiMap.endpoints:
            sc = {k: v for k, v in (("controller", e.controller), ("action", e.action)) if v}
            out["api"][_route_key(e.route, e.method)] = Item(
                "api", f"{e.method.upper()} {e.route}", e.file, scalars=sc,
                details={"handler": f"{e.controller}.{e.action}"})
        for s in snap.discovery.services + snap.discovery.repositories:
            out["service"][_k(s.name)] = Item(
                "service", s.name, s.file, sets={"dependencies": self._deps(snap, s.name, s.file)},
                details={"platform": s.platform})
        for en in snap.entities:
            sc = {f"type:{p}": t for p, t in en.properties.items()}
            out["entity"][_k(en.name)] = Item(
                "entity", en.name, en.file, scalars=sc, sets={"properties": set(en.properties)},
                details={"kind": en.kind, **({"table": en.table} if en.table else {})})
        return out

    # ---- comparison -------------------------------------------------
    @staticmethod
    def _diff(b: Item, e: Item) -> tuple[List[str], List[str]]:
        conflicts, additions = [], []
        for key in sorted(set(b.scalars) & set(e.scalars)):
            if b.scalars[key] != e.scalars[key]:
                conflicts.append(f"{key}: '{b.scalars[key]}' (base) vs '{e.scalars[key]}' (enhancement)")
        for key in sorted(e.sets):
            extra = e.sets[key] - b.sets.get(key, set())
            if extra:
                additions.append(f"adds {key}: {', '.join(sorted(extra))}")
        return conflicts, additions

    def compare(self, base: RepositorySnapshot, enh: RepositorySnapshot) -> ComparisonResult:
        bi, ei = self.items(base), self.items(enh)
        cats: Dict[str, CategoryComparison] = {}
        missing: List[MissingComponent] = []
        modified_all: List[ModifiedComponent] = []
        only_enh: Dict[str, Dict[str, Item]] = {k: {} for k in KIND_ORDER}

        for kind in KIND_ORDER:
            b, e = bi[kind], ei[kind]
            cat = CategoryComparison(base=len(b), enhancement=len(e))
            for key in sorted(set(b) | set(e), key=lambda x: (b.get(x) or e[x]).name):
                if key in b and key in e:
                    conflicts, additions = self._diff(b[key], e[key])
                    if conflicts or additions:
                        mod = ModifiedComponent(kind=kind, name=e[key].name, conflicts=conflicts,
                                                additions=additions, base=b[key].ref(), enhancement=e[key].ref())
                        cat.modified.append(mod)
                        modified_all.append(mod)
                    else:
                        cat.common += 1
                elif key in e:
                    cat.onlyInEnhancement.append(e[key].ref())
                    only_enh[kind][key] = e[key]
                    missing.append(MissingComponent(kind=kind, name=e[key].name, missingFrom="base",
                                                    presentIn="enhancement", file=e[key].file))
                else:
                    cat.onlyInBase.append(b[key].ref())
                    missing.append(MissingComponent(kind=kind, name=b[key].name, missingFrom="enhancement",
                                                    presentIn="base", file=b[key].file))
            cats[kind] = cat

        candidates = self._candidates(enh, only_enh, modified_all)
        plural = {"module": "modules", "route": "routes", "api": "apis", "service": "services", "entity": "entities"}
        summary = {}
        for kind, cat in cats.items():
            p = plural[kind]
            summary.update({f"{p}Base": cat.base, f"{p}Enhancement": cat.enhancement, f"{p}Common": cat.common,
                            f"{p}MissingInBase": len(cat.onlyInEnhancement),
                            f"{p}MissingInEnhancement": len(cat.onlyInBase), f"{p}Modified": len(cat.modified)})
        summary["integrationCandidates"] = len(candidates)

        warnings = list(base.architecture.warnings) + list(enh.architecture.warnings)
        if not base.entities and not enh.entities:
            warnings.append("No database entities were detected in either application.")
        result = ComparisonResult(
            baseApplication=base.architecture.applicationName,
            enhancementApplication=enh.architecture.applicationName,
            summary=summary, modules=cats["module"], routes=cats["route"], apis=cats["api"],
            services=cats["service"], entities=cats["entity"],
            missingComponents=missing, integrationCandidates=candidates, warnings=warnings)
        logger.info("Compared %s vs %s: %s", result.baseApplication, result.enhancementApplication, summary)
        return result

    # ---- integration candidates ------------------------------------
    def _candidates(self, enh: RepositorySnapshot, only_enh: Dict[str, Dict[str, Item]],
                    modified: List[ModifiedComponent]) -> List[IntegrationCandidate]:
        new_names = {_k(i.name): f"{kind}:{i.name}" for kind in ("service", "entity", "module")
                     for i in only_enh[kind].values()}
        raw: List[IntegrationCandidate] = []

        def depends(names: Set[str]) -> List[str]:
            return sorted({new_names[_k(n)] for n in names if _k(n) in new_names})

        for kind in KIND_ORDER:
            for it in only_enh[kind].values():
                deps: List[str] = []
                if kind == "service":
                    deps = depends(it.sets.get("dependencies", set()))
                elif kind in ("route", "api"):
                    handler = it.details.get("handler", "")
                    ctrl = handler.split(".")[0] if "." in handler else ""
                    if ctrl:
                        deps = depends(self._deps(enh, ctrl, None))
                deps = [d for d in deps if d != f"{kind}:{it.name}"]
                raw.append(IntegrationCandidate(
                    order=0, id="", kind=kind, name=it.name, action="add",
                    risk="medium" if deps else "low", sourceFile=it.file, dependsOn=deps,
                    reason="Present in the enhancement but missing from the base"
                           + (f"; needs {', '.join(deps)} first" if deps else "")))
        for m in modified:
            risk = "high" if m.conflicts else "medium"
            parts = [f"Conflict: {c}" for c in m.conflicts] + [a[:1].upper() + a[1:] for a in m.additions]
            raw.append(IntegrationCandidate(
                order=0, id="", kind=m.kind, name=m.name, action="merge", risk=risk,
                sourceFile=m.enhancement.file, conflicts=m.conflicts,
                reason="Exists in both with differences: " + "; ".join(parts)))

        raw.sort(key=lambda c: (KIND_ORDER.index(c.kind), 0 if c.action == "add" else 1, c.name.lower()))
        for i, c in enumerate(raw, 1):
            c.order, c.id = i, f"IC-{i:03d}"
        return raw

    def run(self, base_root: Path, enhancement_root: Path) -> ComparisonResult:
        return self.compare(self.analyze(base_root), self.analyze(enhancement_root))
