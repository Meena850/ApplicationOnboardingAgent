"""Impact analysis: which parts of the BASE application are affected by integrating the enhancement at the
recommended integration points. Deterministic (dependency-graph traversal), no AI.

Scoring (per affected item, 0-100):
  seed power P  = 50 conflicting change | 25 additive change | 10 wiring only (entry point / route table)
  score         = P at the integration point (distance 0); P * {1: .6, 2: .35, 3: .2} for dependents
                  (+12 if >=5 items depend on it, +6 if >=2, +10 shared layout); 10 for newly added items
  level         = High >= 50, Medium >= 20, otherwise Low
"""
import logging
import posixpath
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.agents.comparison_agent import RepositoryComparisonAgent
from app.agents.recommendation_agent import IntegrationRecommendationAgent
from app.models.comparison import RepositorySnapshot
from app.models.impact import (
    AffectedItem, CategoryImpact, ImpactAnalysisResult, IntegrationPointImpact,
)
from app.models.recommendation import IntegrationRecommendationResult, RecommendedLocation

logger = logging.getLogger(__name__)

CATEGORY = {"controller": "controllers", "service": "services", "component": "components",
            "route": "routes", "api": "apis"}
NAMED_KINDS = {"controller", "service", "component"}
DECAY = {1: 0.6, 2: 0.35, 3: 0.2}
MAX_DEPTH = 3
P_CONFLICT, P_ADDITIVE, P_WIRING, P_ADDED = 50, 25, 10, 10
HIGH, MEDIUM = 50, 20
LEVEL_RANK = {"Low": 0, "Medium": 1, "High": 2}


def level_of(score: int) -> str:
    return "High" if score >= HIGH else "Medium" if score >= MEDIUM else "Low"


def _type_usage(name: str) -> "re.Pattern[str]":
    """Matches real uses of a type (declarations, generics, new, static access, @model), not plain words
    in labels or prose."""
    n = re.escape(name)
    return re.compile(
        rf"@model\s+[\w.<>]*\b{n}\b|<\s*[\w.]*\b{n}\b\s*[>,]|\bnew\s+{n}\b|\b{n}\.\w+"
        rf"|\b{n}\??(?:\[\])?\s+\w+\s*[=;,)(]|:\s*{n}\b|\b{n}\s*\{{")


def _label(i: AffectedItem) -> str:
    kind = "api" if i.category == "apis" else i.category[:-1]
    return f"{kind} {i.name}"


@dataclass(frozen=True)
class Node:
    kind: str
    name: str
    file: str

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.name}"


class Graph:
    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.by_file: Dict[str, List[Node]] = defaultdict(list)
        self.by_name: Dict[str, Node] = {}
        self.dependents: Dict[str, Set[str]] = defaultdict(set)  # target -> things that depend on it
        self.deps: Dict[str, Set[str]] = defaultdict(set)  # thing -> what it depends on

    def add(self, kind: str, name: str, file: str) -> Node:
        node = Node(kind, name, file)
        if node.id in self.nodes:
            return self.nodes[node.id]
        self.nodes[node.id] = node
        self.by_file[file].append(node)
        if kind in NAMED_KINDS:
            self.by_name.setdefault(name.lower(), node)
        return node

    def link(self, dependent: Node, target: Node) -> None:
        if dependent.id != target.id:
            self.dependents[target.id].add(dependent.id)
            self.deps[dependent.id].add(target.id)


def build_graph(snap: RepositorySnapshot) -> Graph:
    g, d, a = Graph(), snap.discovery, snap.architecture
    for c in d.controllers:
        g.add("controller", c.name, c.file)
    for s in d.services + d.repositories:
        g.add("service", s.name, s.file)
    for c in d.components + d.views + d.layouts:
        g.add("component", c.name, c.file)
    for p in d.pages:
        g.add("component", p.name, p.file)
    for r in a.routeMap.routes:
        g.add("route", f"{(r.method or 'GET').upper()} {r.path}", r.file)
    for e in a.apiMap.endpoints:
        g.add("api", f"{e.method.upper()} {e.route}", e.file)

    for e in a.dependencyMap.internal:
        if e.kind == "injects":
            s, t = g.by_name.get(e.source.lower()), g.by_name.get(e.target.lower())
            if s and t:
                g.link(s, t)
        else:  # imports: file -> file
            for s in g.by_file.get(e.source, []):
                for t in g.by_file.get(e.target, []):
                    if s.kind in NAMED_KINDS and t.kind in NAMED_KINDS:
                        g.link(s, t)
    for r in a.routeMap.routes:
        rn = g.nodes.get(f"route:{(r.method or 'GET').upper()} {r.path}")
        h = r.handler or ""
        if not rn or not h:
            continue
        if "." in h:
            ctrl = g.by_name.get(h.split(".")[0].lower())
            if ctrl:
                g.link(rn, ctrl)
                for vn in g.by_file.get(r.view or "", []):
                    if vn.kind == "component":
                        g.link(vn, ctrl)
        else:
            comp = g.by_name.get(h.lower())
            if comp:
                g.link(rn, comp)
    for e in a.apiMap.endpoints:
        an, ctrl = g.nodes.get(f"api:{e.method.upper()} {e.route}"), g.by_name.get((e.controller or "").lower())
        if an and ctrl:
            g.link(an, ctrl)
    return g


class ImpactAnalysisAgent:
    def __init__(self, recommender: IntegrationRecommendationAgent | None = None) -> None:
        self.recommender = recommender or IntegrationRecommendationAgent()
        self._text: Dict[Tuple[str, str], str] = {}

    def analyze_and_assess(self, base_root: Path, enh_root: Path, top_n: Optional[int] = None) -> ImpactAnalysisResult:
        comparer: RepositoryComparisonAgent = self.recommender.comparer
        return self.assess(comparer.analyze(base_root), comparer.analyze(enh_root), top_n=top_n)

    # ------------------------------------------------------------
    def assess(self, base: RepositorySnapshot, enh: RepositorySnapshot,
               recommendation: Optional[IntegrationRecommendationResult] = None,
               top_n: Optional[int] = None) -> ImpactAnalysisResult:
        rec = recommendation or self.recommender.recommend(base, enh, limit=top_n)
        g, eg = build_graph(base), build_graph(enh)
        base_root = Path(base.architecture.repositoryPath)
        entry_files = {e.file for e in base.discovery.entryPoints}
        route_files = {r.file for r in base.discovery.routes if r.source == "react-router"}
        entity_by_file = {e.file: e.name for e in base.entities}
        warnings = list(rec.warnings)

        items: Dict[str, dict] = {}

        def touch(node: Node, score: int, change: str, distance: int, reason: str, point: str,
                  file: Optional[str] = None) -> None:
            it = items.setdefault(node.id, dict(node=node, score=0, change=change, distance=distance,
                                                reasons=[], points=[], file=file or node.file))
            if score > it["score"] or (score == it["score"] and distance < it["distance"]):
                it.update(score=score, change=change, distance=distance)
            if reason not in it["reasons"]:
                it["reasons"].append(reason)
            if point not in it["points"]:
                it["points"].append(point)

        def propagate(seed: Node, power: int, point: str, why: str) -> None:
            seen = {seed.id}
            queue = deque([(seed, 0)])
            while queue:
                node, dist = queue.popleft()
                if dist >= MAX_DEPTH:
                    continue
                for dep_id in sorted(g.dependents.get(node.id, ())):
                    if dep_id in seen:
                        continue
                    seen.add(dep_id)
                    dep = g.nodes[dep_id]
                    touch(dep, round(power * DECAY[dist + 1]), "dependent", dist + 1,
                          f"Depends on {node.kind} '{node.name}' ({why})", point)
                    queue.append((dep, dist + 1))

        point_scores: Dict[str, int] = {}
        for r in rec.recommendations:
            point = r.filePath
            if r.action == "modify":
                self._modify(r, g, base, base_root, entity_by_file, entry_files, route_files,
                             touch, propagate, point_scores)
            else:
                self._create(r, g, eg, enh, touch, point_scores)

        out = self._finalize(items, g)
        result = self._result(base, enh, rec, out, point_scores, warnings)
        logger.info("Impact %s -> %s: %s (%d)", result.enhancementApplication, result.baseApplication,
                    result.overallLevel, result.overallScore)
        return result

    # ---- seeds -------------------------------------------------
    def _modify(self, r: RecommendedLocation, g: Graph, base: RepositorySnapshot, base_root: Path,
                entity_by_file: Dict[str, str], entry_files: Set[str], route_files: Set[str],
                touch, propagate, point_scores: Dict[str, int]) -> None:
        file = r.filePath
        conflict = any(e.startswith("Conflict") for e in r.evidence)
        wiring = file in entry_files or file in route_files
        power = P_WIRING if wiring else P_CONFLICT if conflict else P_ADDITIVE
        what = ("wiring only" if wiring else "conflicting change" if conflict else "additive change")
        why = f"modified at '{file}': {what}"
        point_scores[file] = max(point_scores.get(file, 0), power + (3 * len(r.supports) if wiring else 0))

        for node in g.by_file.get(file, []):
            if node.kind in NAMED_KINDS or (file in route_files and node.kind == "route"):
                touch(node, power, "modified", 0, f"Edited at integration point '{file}' ({what})", file)
                propagate(node, power, file, why)

        entity = entity_by_file.get(file)
        if entity:  # entity shape changes ripple to code that actually uses the type
            use = _type_usage(entity)
            for node in g.nodes.values():
                if node.kind in NAMED_KINDS and node.file != file and use.search(self._read(base_root, node.file)):
                    touch(node, round(power * DECAY[1]), "dependent", 1,
                          f"References entity '{entity}' ({why})", file)
                    propagate(node, power, file, f"references changed entity '{entity}'")
            point_scores[file] = max(point_scores[file], power)

    def _create(self, r: RecommendedLocation, g: Graph, eg: Graph, enh: RepositorySnapshot,
                touch, point_scores: Dict[str, int]) -> None:
        point = r.filePath
        added: List[Tuple[Node, str]] = []
        for sug in r.suggestedFiles:
            nodes = eg.by_file.get(sug) or [n for f, ns in eg.by_file.items()
                                            if posixpath.basename(f) == posixpath.basename(sug) for n in ns]
            added += [(n, sug) for n in nodes]
        for node, target in added:
            touch(node, P_ADDED, "added", 0, f"New in the enhancement; to be created under '{point}'", point, target)
            for dep_id in eg.deps.get(node.id, ()):  # base code that the new code will start to consume
                dep = eg.nodes[dep_id]
                base_node = g.nodes.get(dep.id) or (g.by_name.get(dep.name.lower()) if dep.kind in NAMED_KINDS else None)
                if base_node:
                    touch(base_node, 6, "dependent", 1,
                          f"Gains a new consumer: {node.kind} '{node.name}' from the enhancement", point)
        point_scores[point] = max(point_scores.get(point, 0), P_ADDED + (3 * max(0, len(added) - 1)))

    # ---- results -----------------------------------------------
    def _read(self, root: Path, rel: str) -> str:
        key = (str(root), rel)
        if key not in self._text:
            try:
                self._text[key] = (root / rel).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                self._text[key] = ""
        return self._text[key]

    @staticmethod
    def _finalize(items: Dict[str, dict], g: Graph) -> Dict[str, List[AffectedItem]]:
        out: Dict[str, List[AffectedItem]] = {c: [] for c in CATEGORY.values()}
        for nid, it in items.items():
            node: Node = it["node"]
            score = it["score"]
            if it["change"] != "added":
                fan = len(g.dependents.get(nid, ()))
                bonus = 12 if fan >= 5 else 6 if fan >= 2 else 0
                if "layout" in node.name.lower():
                    bonus += 10
                if bonus:
                    score += bonus
                    it["reasons"].append(f"{fan} other item(s) depend on it" if fan >= 2 else "Shared layout")
            if len(it["points"]) > 1:
                score += 5
            score = min(100, score)
            out[CATEGORY[node.kind]].append(AffectedItem(
                category=CATEGORY[node.kind], name=node.name, file=it["file"], level=level_of(score),
                score=score, change=it["change"], distance=it["distance"], reasons=it["reasons"][:5],
                integrationPoints=it["points"]))
        for lst in out.values():
            lst.sort(key=lambda i: (-i.score, i.name))
        return out

    def _result(self, base: RepositorySnapshot, enh: RepositorySnapshot, rec: IntegrationRecommendationResult,
                out: Dict[str, List[AffectedItem]], point_scores: Dict[str, int],
                warnings: List[str]) -> ImpactAnalysisResult:
        cats: Dict[str, CategoryImpact] = {}
        everything: List[AffectedItem] = []
        for name, lst in out.items():
            cats[name] = CategoryImpact(
                total=len(lst), low=sum(i.level == "Low" for i in lst), medium=sum(i.level == "Medium" for i in lst),
                high=sum(i.level == "High" for i in lst), items=lst)
            everything += lst
        top = max((i.score for i in everything), default=0)
        n_high, n_med = sum(i.level == "High" for i in everything), sum(i.level == "Medium" for i in everything)
        overall = "High" if n_high or n_med >= 5 else "Medium" if n_med else "Low"
        score = min(100, top + 2 * len(everything))
        if not rec.recommendations:
            warnings.append("No integration points were recommended, so no impact was assessed.")

        points = []
        for r in rec.recommendations:
            touched = [i for i in everything if r.filePath in i.integrationPoints]
            sc = max([point_scores.get(r.filePath, 0)] + [i.score for i in touched if i.change != "added"])
            points.append(IntegrationPointImpact(
                filePath=r.filePath, action=r.action, level=level_of(sc), score=sc,
                summary=f"{r.action.capitalize()}: {r.reason}", affectedCount=len(touched)))
        points.sort(key=lambda p: (-p.score, p.filePath))

        base_name, enh_name = base.architecture.applicationName, enh.architecture.applicationName
        worst = [i for i in sorted(everything, key=lambda i: -i.score) if i.level != "Low"][:3]
        highlights = ", ".join(_label(i) for i in worst)
        summary = (f"Integrating '{enh_name}' into '{base_name}' at {len(rec.recommendations)} integration point(s) "
                   f"affects {len(everything)} item(s) ({n_high} High, {n_med} Medium, "
                   f"{len(everything) - n_high - n_med} Low). Overall impact: {overall} (score {score}/100)."
                   + (f" Highest impact: {highlights}." if worst else ""))
        result = ImpactAnalysisResult(
            baseApplication=base_name, enhancementApplication=enh_name, overallLevel=overall, overallScore=score,
            summary=summary, components=cats["components"], routes=cats["routes"], apis=cats["apis"],
            controllers=cats["controllers"], services=cats["services"], integrationPoints=points,
            warnings=warnings)
        result.summaryReport = self._markdown(result)
        return result

    @staticmethod
    def _markdown(r: ImpactAnalysisResult) -> str:
        lines = [f"# Impact Analysis: {r.enhancementApplication} → {r.baseApplication}", "",
                 f"**Overall impact: {r.overallLevel}** (score {r.overallScore}/100)", "", r.summary, "",
                 "## Affected items", "", "| Category | Total | High | Medium | Low |", "|---|---|---|---|---|"]
        for name in ("components", "routes", "apis", "controllers", "services"):
            c: CategoryImpact = getattr(r, name)
            lines.append(f"| {name.capitalize()} | {c.total} | {c.high} | {c.medium} | {c.low} |")
        lines += ["", "## Integration points", "", "| File | Action | Impact | Affected |", "|---|---|---|---|"]
        lines += [f"| `{p.filePath}` | {p.action} | {p.level} ({p.score}) | {p.affectedCount} |" for p in r.integrationPoints]
        for level in ("High", "Medium", "Low"):
            rows = [i for n in ("controllers", "services", "components", "routes", "apis")
                    for i in getattr(r, n).items if i.level == level]
            if not rows:
                continue
            lines += ["", f"## {level} impact", ""]
            for i in sorted(rows, key=lambda x: -x.score):
                lines.append(f"- **{_label(i)}** "
                             f"({i.change}, score {i.score}): {i.reasons[0] if i.reasons else ''}")
        if r.warnings:
            lines += ["", "## Warnings", ""] + [f"- {w}" for w in r.warnings]
        return "\n".join(lines) + "\n"
