import logging
import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.agents.comparison_agent import RepositoryComparisonAgent, _k
from app.models.comparison import ComparisonResult, ComponentRef, RepositorySnapshot
from app.models.recommendation import IntegrationRecommendationResult, RecommendedLocation

logger = logging.getLogger(__name__)
TOP_N = 3
MAX_EVIDENCE = 8


@dataclass
class Slot:
    path: str
    loc_type: str  # file | directory
    action: str  # create | modify
    label: str  # human label of what goes here
    names: List[str] = field(default_factory=list)
    supports: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    diffs: List[str] = field(default_factory=list)
    suggested: List[str] = field(default_factory=list)
    convention: int = 0  # how many existing base files back this location
    matched: int = 0  # supported items whose enhancement path equals this location
    conflicts: int = 0
    fallback: bool = False
    affinity: Optional[str] = None  # business term shared with an existing base module, e.g. "report"

    def add(self, kind: str, name: str, enh_file: Optional[str], matched: bool) -> None:
        if name not in self.names:
            self.names.append(name)
        tag = f"{kind}:{name}"
        if tag not in self.supports:
            self.supports.append(tag)
            self.matched += 1 if matched else 0

    def note(self, text: str) -> None:
        if text not in self.evidence:
            self.evidence.append(text)

    @property
    def confidence(self) -> int:
        c = 50
        c += 15 if self.convention >= 2 else 8 if self.convention == 1 else 0
        if self.supports and self.matched == len(self.supports):
            c += 10
        c += min(15, 5 * len(self.supports))
        if self.affinity:
            c += 15  # an existing module already covers this business area
        if self.conflicts:
            c -= 20
        if self.fallback:
            c -= 15
        return max(5, min(97, c))

    @property
    def score(self) -> int:
        """Ranking only (confidence is reported separately). Wiring that would break the app if skipped
        (DI registrations / entry point) and conflict sites that need a decision rank higher."""
        bonus = (20 if self.label == "entry point" else 0) + (10 if self.conflicts else 0)
        return len(self.supports) * 10 + self.confidence + bonus

    @property
    def priority(self) -> int:
        """Tie-break: entry point, then user-facing surface, then logic, then data, then views/pages."""
        order = {"entry point": 0, "route table": 1, "controller": 1, "controllers": 1, "Razor pages": 1,
                 "services": 2, "entities/models": 3, "views": 4, "pages": 4}
        return order.get(self.label, 5)

    @property
    def reason(self) -> str:
        names = ", ".join(self.names)
        if self.action == "create":
            if self.affinity:
                return (f"Existing {self.affinity} module present in '{self.path}' "
                        f"({self.convention} file(s)); the enhancement's {', '.join(self.names)} belongs with it.")
            if self.fallback:
                return (f"The enhancement adds {names}, and the base has no established location for {self.label}; "
                        f"'{self.path}' mirrors the enhancement's own layout.")
            return (f"Create the missing {self.label} in '{self.path}': the base already keeps its "
                    f"{self.convention} existing {self.label} there, and the enhancement adds {names}.")
        detail = "; ".join(self.diffs[:3])
        return f"Modify '{self.path}' to integrate {names}" + (f": {detail}." if detail else ".")


def _convention(files: List[str]) -> Optional[Tuple[str, int, List[str]]]:
    dirs = Counter(posixpath.dirname(f) for f in files)
    if not dirs:
        return None
    d, n = dirs.most_common(1)[0]
    return d, n, sorted(posixpath.basename(f) for f in files if posixpath.dirname(f) == d)


def _dir_label(d: str) -> str:
    return d + "/" if d else "./"


_GENERIC = {"controller", "service", "page", "view", "model", "index", "list", "details", "detail", "get",
            "post", "put", "delete", "home", "i", "repository", "component", "app", "main"}
_GENERIC_DIRS = {"src", "pages", "page", "components", "component", "services", "service", "controllers",
                 "controller", "models", "model", "views", "view", "shared", "app", "lib", "hooks", "utils"}


def _stem(word: str) -> str:
    w = word.lower()
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def _tokens(name: str) -> List[str]:
    words = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]+|[a-z0-9]+", name)
    return [_stem(w) for w in words if w.lower() not in _GENERIC and len(w) > 2]


def _affinity(name: str, enh_file: str, base_files: List[str]) -> Optional[Tuple[str, str, int, List[str]]]:
    """Find an existing base directory named after the business area of the new item (e.g. 'reports')."""
    wanted = set(_tokens(name)) | set(_tokens(posixpath.splitext(posixpath.basename(enh_file))[0]))
    best: Optional[Tuple[str, str, int, List[str]]] = None
    dirs = Counter(posixpath.dirname(f) for f in base_files)
    for d, n in dirs.items():
        segs = [_stem(s) for s in d.split("/") if s and s.lower() not in _GENERIC_DIRS]
        hit = next((t for t in sorted(wanted) if t in segs), None)
        if hit and (best is None or n > best[2]):
            best = (hit, d, n, sorted(posixpath.basename(f) for f in base_files if posixpath.dirname(f) == d))
    return best


class IntegrationRecommendationAgent:
    """Recommends WHERE in the base application the enhancement should be integrated.

    Deterministic: derives locations from the base's own structure (where it keeps services, controllers,
    views, entities, routes, DI registrations) and from what the comparison found missing or conflicting.
    Confidence = 50 + convention strength (+15/+8) + same-path match (+10) + support (+5 each, max 15)
    - conflicts (20) - fallback guess (15).
    """

    def __init__(self, comparer: RepositoryComparisonAgent | None = None) -> None:
        self.comparer = comparer or RepositoryComparisonAgent()

    def analyze_and_recommend(self, base_root: Path, enh_root: Path) -> IntegrationRecommendationResult:
        return self.recommend(self.comparer.analyze(base_root), self.comparer.analyze(enh_root))

    # ------------------------------------------------------------
    def recommend(self, base: RepositorySnapshot, enh: RepositorySnapshot,
                  comparison: Optional[ComparisonResult] = None,
                  limit: Optional[int] = TOP_N) -> IntegrationRecommendationResult:
        """limit=None returns every considered location (used by impact analysis)."""
        cmp = comparison or self.comparer.compare(base, enh)
        slots: Dict[Tuple[str, str], Slot] = {}
        warnings: List[str] = []
        bd = base.discovery

        def slot(path: str, loc: str, action: str, label: str) -> Slot:
            return slots.setdefault((path, action), Slot(path=path, loc_type=loc, action=action, label=label))

        def create(label: str, kind: str, name: str, enh_file: str, base_files: List[str],
                   conv: Optional[Tuple[str, int, List[str]]] = None) -> None:
            conv = conv or _convention(base_files)
            aff = _affinity(name, enh_file, base_files)
            if aff:
                conv = (aff[1], aff[2], aff[3])
            if conv:
                d, n, sibs = conv
            else:
                d, n, sibs = posixpath.dirname(enh_file), 0, []
            s = slot(_dir_label(d), "directory", "create", label)
            s.convention, s.fallback = n, conv is None
            if aff:
                s.affinity = aff[0]
                s.note(f"Existing '{aff[0]}' module found in '{d}/' ({n} file(s): {', '.join(sibs[:5])}); "
                       f"{name} shares the '{aff[0]}' business term")
            s.add(kind, name, enh_file, posixpath.dirname(enh_file) == d)
            sug = posixpath.join(d, posixpath.basename(enh_file))
            if sug not in s.suggested:
                s.suggested.append(sug)
            if conv:
                s.note(f"Base keeps {n} {label} file(s) in '{d or '.'}/': {', '.join(sibs[:5])}")
            else:
                s.note(f"Base has no existing {label}; using the enhancement's location '{d or '.'}/'")
            s.note(f"Enhancement adds {name} at '{enh_file}' (missing from base)")

        def modify(label: str, kind: str, name: str, base_file: str, enh_file: Optional[str],
                   diff: str, conflict: bool = False, convention: int = 2) -> None:
            s = slot(base_file, "file", "modify", label)
            s.convention = max(s.convention, convention)
            s.add(kind, name, enh_file, enh_file == base_file)
            s.diffs.append(diff)
            s.note(f"Base already contains '{base_file}'")
            s.note(diff)
            if conflict:
                s.conflicts += 1

        base_ctrl = {_k(c.name): c for c in bd.controllers}
        ctrl_files = [c.file for c in bd.controllers]
        react_route_files = Counter(r.file for r in bd.routes if r.source == "react-router")
        entry = bd.entryPoints[0].file if bd.entryPoints else None

        def route_like(kind: str, ref: ComponentRef) -> None:
            handler, src = ref.details.get("handler", ""), ref.details.get("source", "")
            if src == "react-router" and react_route_files:
                f, n = react_route_files.most_common(1)[0]
                modify("route table", kind, ref.name, f, ref.file,
                       f"Add route {ref.name} → {handler or 'component'}", convention=2 if n > 1 else 1)
            elif src == "minimal-api" and entry:
                modify("entry point", kind, ref.name, entry, ref.file, f"Map endpoint {ref.name}", convention=1)
            elif src == "razor-page":
                pages = [p.file for p in bd.pages if p.type == "razor-page"]
                create("Razor pages", kind, ref.name, ref.file, pages)
            elif "." in handler and not handler.startswith("None"):
                ctrl = handler.split(".")[0]
                if _k(ctrl) in base_ctrl:
                    modify("controller", kind, ref.name, base_ctrl[_k(ctrl)].file, ref.file,
                           f"Add action {handler} for {ref.name}")
                else:
                    create("controllers", kind, ref.name, ref.file, ctrl_files)

        # --- missing in base -------------------------------------
        for ref in cmp.routes.onlyInEnhancement:
            route_like("route", ref)
        for ref in cmp.apis.onlyInEnhancement:
            route_like("api", ref)
        for ref in cmp.services.onlyInEnhancement:
            plat = ref.details.get("platform")
            files = [s.file for s in bd.services + bd.repositories if s.platform == plat]
            create("services", "service", ref.name, ref.file or "", files)
        for ref in cmp.entities.onlyInEnhancement:
            create("entities/models", "entity", ref.name, ref.file or "", [e.file for e in base.entities])

        base_views = Counter(Path(v.file).parts[0] for v in bd.views if Path(v.file).parts)
        base_view_keys = {_k(v.name) for v in bd.views}
        for v in enh.discovery.views:
            if _k(v.name) in base_view_keys:
                continue
            root = Path(v.file).parts[0] if Path(v.file).parts else ""
            conv = (posixpath.dirname(v.file), base_views[root], []) if root in base_views else None
            create("views", "view", v.name, v.file, [], conv)
        base_page_keys = {_k(p.name) for p in bd.pages}
        react_pages = [p.file for p in bd.pages if p.type == "react"]
        for p in enh.discovery.pages:
            if p.type == "react" and _k(p.name) not in base_page_keys:
                create("pages", "page", p.name, p.file, react_pages)

        base_regs = {(r.service, r.implementation) for r in base.architecture.dependencyMap.registrations}
        new_regs = [r for r in enh.architecture.dependencyMap.registrations
                    if (r.service, r.implementation) not in base_regs]
        if new_regs and entry:
            for r in {(x.service, x.implementation, x.lifetime): x for x in new_regs}.values():
                modify("entry point", "registration", r.implementation, entry, r.file,
                       f"Register {r.service} → {r.implementation} ({r.lifetime})", convention=1)
            slots[(entry, "modify")].note(
                f"Base entry point already registers {len(base_regs)} service(s); enhancement registers "
                f"{len(new_regs)} that the base lacks")
        elif new_regs:
            warnings.append("Enhancement registers services but no base entry point (Program.cs) was found.")

        # --- exists in both, but differs -------------------------
        for cat in (cmp.entities, cmp.services, cmp.apis, cmp.routes):
            for m in cat.modified:
                if not m.base.file:
                    continue
                diffs = [f"Conflict: {c}" for c in m.conflicts] + [a[:1].upper() + a[1:] for a in m.additions]
                for i, d in enumerate(diffs):
                    modify(m.kind if m.kind != "entity" else "entity", m.kind, m.name, m.base.file,
                           m.enhancement.file, d, conflict=d.startswith("Conflict") and i == 0)

        if not slots:
            warnings.append("The enhancement adds nothing the base lacks; no integration location is needed.")
        ranked = sorted(slots.values(), key=lambda s: (-s.score, s.priority, s.path))[:limit]
        recs = [RecommendedLocation(
            rank=i, filePath=s.path, locationType=s.loc_type, action=s.action, reason=s.reason,
            confidence=s.confidence, confidenceLabel=f"{s.confidence}%", evidence=s.evidence[:MAX_EVIDENCE],
            supports=s.supports,
            suggestedFiles=s.suggested) for i, s in enumerate(ranked, 1)]
        result = IntegrationRecommendationResult(
            baseApplication=base.architecture.applicationName,
            enhancementApplication=enh.architecture.applicationName,
            recommendations=recs, locationsConsidered=len(slots), warnings=warnings)
        logger.info("Recommended %d of %d locations for %s", len(recs), len(slots), result.baseApplication)
        return result
