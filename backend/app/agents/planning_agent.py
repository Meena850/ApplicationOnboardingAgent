"""Implementation planning: turns the impact analysis (+ recommended integration points) into a phased,
dependency-ordered task list. Deterministic            if kind in ("route", "api"):
                # new controller => "controller"; editing an existing controller file => "controller";
                # editing a route table / entry point (React router, Program.cs minimal APIs) => "routing"
                is_controller_file = r.action == "create" or (
                    r.filePath.endswith(".cs") and not r.filePath.endswith(("Program.cs", "Startup.cs")))
                cat = "controller" if is_controller_file else "routing"I.

Layer order (which decides phases and task dependencies):
  Phase 1  data -> service -> wiring (DI registration / entry point)
  Phase 2  controller -> ui (pages/views) -> routing
  Phase 3  verification of affected existing code, regression, end-to-end, final build
"""
import logging
import posixpath
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.agents.impact_agent import ImpactAnalysisAgent, LEVEL_RANK
from app.models.impact import AffectedItem, ImpactAnalysisResult, IntegrationPointImpact
from app.models.plan import ImplementationPlan, PlanPhase, PlanTask
from app.models.recommendation import IntegrationRecommendationResult, RecommendedLocation

logger = logging.getLogger(__name__)

CAT_ORDER = ["data", "service", "wiring", "controller", "ui", "routing", "verify"]
PHASE_OF = {"data": 1, "service": 1, "wiring": 1, "controller": 2, "ui": 2, "routing": 2, "verify": 3}
DEPENDS = {"service": ["data"], "wiring": ["service"], "controller": ["service", "wiring", "data"],
           "ui": ["controller", "service"], "routing": ["ui", "controller", "service"]}
PHASES = {
    1: ("Foundation: data, services and wiring",
        "Land the pieces everything else builds on, with no user-visible change yet.",
        ["The solution builds with the new/changed entities and services",
         "The application starts and every new service resolves from the container"]),
    2: ("Feature surface: controllers, pages/views and routes",
        "Expose the enhancement to users on top of the foundation.",
        ["New controllers, pages/views and routes are reachable",
         "Existing routes still resolve (nothing is shadowed or broken)"]),
    3: ("Verification: affected code and regression",
        "Prove the change is safe: update and verify existing code that depends on what changed.",
        ["All regression checks pass", "Every High and Medium impact item has been verified"]),
}
JS_EXT = (".ts", ".tsx", ".js", ".jsx")
KIND_TO_CAT = {"entity": "data", "service": "service", "registration": "wiring", "controller": "controller",
               "route": "controller", "api": "controller", "view": "ui", "page": "ui"}


@dataclass
class _Task:
    category: str
    title: str
    description: str
    files: List[str]
    validation: List[str]
    level: str
    key: str = ""
    deps: List[int] = field(default_factory=list)


def _join(names: List[str], limit: int = 4) -> str:
    names = list(dict.fromkeys(names))
    return ", ".join(names[:limit]) + (f" (+{len(names) - limit} more)" if len(names) > limit else "")


def _max_level(levels: List[str]) -> str:
    return max(levels, key=lambda lv: LEVEL_RANK[lv], default="Low")


def _effort(files: List[str], level: str) -> str:
    return "L" if level == "High" or len(files) >= 6 else "S" if len(files) <= 2 and level == "Low" else "M"


class ImplementationPlanningAgent:
    def __init__(self, impact_agent: ImpactAnalysisAgent | None = None) -> None:
        self.impact_agent = impact_agent or ImpactAnalysisAgent()

    def analyze_and_plan(self, base_root: Path, enh_root: Path, top_n: Optional[int] = None) -> ImplementationPlan:
        recommender = self.impact_agent.recommender
        base, enh = recommender.comparer.analyze(base_root), recommender.comparer.analyze(enh_root)
        rec = recommender.recommend(base, enh, limit=top_n)
        return self.plan(self.impact_agent.assess(base, enh, recommendation=rec), rec)

    # ------------------------------------------------------------
    def plan(self, impact: ImpactAnalysisResult,
             recommendation: Optional[IntegrationRecommendationResult] = None) -> ImplementationPlan:
        warnings = list(impact.warnings)
        items = [i for c in (impact.components, impact.routes, impact.apis, impact.controllers, impact.services)
                 for i in c.items]
        if recommendation:
            recs = recommendation.recommendations
        else:
            recs = self._derive(impact, items)
            warnings.append("No recommendation supplied; tasks were derived from the impact data only.")
        points = {p.filePath: p for p in impact.integrationPoints}
        stacks = self._stacks([i.file or "" for i in items] + [r.filePath for r in recs])

        tasks: List[_Task] = []
        for r in recs:
            tasks += self._point_tasks(r, points.get(r.filePath), stacks, warnings)
        tasks.sort(key=lambda t: (PHASE_OF[t.category], CAT_ORDER.index(t.category), t.title))
        planned = len(tasks)
        tasks += self._verification_tasks(impact, items, stacks)

        # dependencies by layer; phase-3 tasks wait for everything before them
        for idx, t in enumerate(tasks):
            if t.category == "verify":
                t.deps = list(range(idx)) if t.title.startswith("Final") else list(range(planned))
            else:
                t.deps = [j for j, o in enumerate(tasks[:planned]) if o.category in DEPENDS.get(t.category, [])]
        out = []
        for idx, t in enumerate(tasks):
            out.append(PlanTask(
                id=f"T{idx + 1}", phase=PHASE_OF[t.category], category=t.category, title=t.title,
                description=t.description, files=t.files, dependsOn=[f"T{j + 1}" for j in t.deps],
                validation=t.validation, level=t.level, effort=_effort(t.files, t.level)))

        phases = [PlanPhase(number=n, name=PHASES[n][0], goal=PHASES[n][1],
                            tasks=[t for t in out if t.phase == n], exitCriteria=PHASES[n][2]) for n in (1, 2, 3)]
        risky = max(out, key=lambda t: LEVEL_RANK[t.level], default=None)
        summary = (f"{len(out)} task(s) in 3 phases to integrate '{impact.enhancementApplication}' into "
                   f"'{impact.baseApplication}' (overall impact {impact.overallLevel}, {impact.overallScore}/100). "
                   + " ".join(f"Phase {p.number}: {len(p.tasks)}." for p in phases)
                   + (f" Start with: {out[0].title}." if out else "")
                   + (f" Highest-risk task: {risky.title} ({risky.level})." if risky and risky.level != "Low" else ""))
        plan = ImplementationPlan(
            baseApplication=impact.baseApplication, enhancementApplication=impact.enhancementApplication,
            overallImpact=impact.overallLevel, overallScore=impact.overallScore, summary=summary,
            phases=phases, taskCount=len(out), warnings=warnings)
        plan.planMarkdown = self._markdown(plan)
        logger.info("Plan %s -> %s: %d tasks", plan.enhancementApplication, plan.baseApplication, len(out))
        return plan

    # ---- tasks from integration points --------------------------
    @staticmethod
    def _stacks(files: List[str]) -> Dict[str, bool]:
        return {"dotnet": any(f.endswith((".cs", ".cshtml", ".csproj")) for f in files),
                "js": any(f.endswith(JS_EXT) for f in files)}

    @staticmethod
    def _build(stacks: Dict[str, bool]) -> str:
        cmds = (["dotnet build"] if stacks["dotnet"] else []) + (["npm run build"] if stacks["js"] else [])
        return " and ".join(cmds) or "the project build"

    def _point_tasks(self, r: RecommendedLocation, point: Optional[IntegrationPointImpact],
                     stacks: Dict[str, bool], warnings: List[str]) -> List[_Task]:
        level = point.level if point else "Low"
        build = self._build(stacks)
        groups: Dict[tuple, List[str]] = {}
        for tag in r.supports:
            kind, _, name = tag.partition(":")
            cat = KIND_TO_CAT.get(kind)
            if kind == "route" or kind == "api":
                cat = "routing" if (r.action == "modify" and (r.filePath.endswith(JS_EXT)
                                                              or not r.filePath.endswith(".cs"))
                                    and not r.filePath.endswith("Controller.cs")) else "controller"
                if r.action == "modify" and r.filePath.endswith(("Program.cs", "Startup.cs")):
                    cat = "routing"
            if cat is None:
                continue
            groups.setdefault((cat, kind if cat == "ui" else ""), []).append(name)
        if not groups:
            warnings.append(f"Could not derive tasks for integration point '{r.filePath}'.")
            return []

        conflicts = [e for e in r.evidence if e.startswith("Conflict")]
        adds = [e for e in r.evidence if e.lower().startswith(("adds ", "register", "add "))]
        out: List[_Task] = []
        for (cat, sub), names in groups.items():
            files = list(r.suggestedFiles) if r.action == "create" and r.suggestedFiles else [r.filePath]
            n = _join(names)
            desc = r.reason
            val: List[str] = []
            if cat == "data":
                title = (f"Resolve conflicts in {n} entity" if conflicts
                         else f"Update {n} entity" if r.action == "modify" else f"Add {n} entity")
                val = [f"Compiles: {build}", f"Review schema/data impact (migration or seed data) for {n}",
                       f"Code that uses {n} still compiles and behaves the same"]
            elif cat == "service":
                title = f"Extend {n}" if r.action == "modify" else f"Add {n} service"
                val = [f"Compiles: {build}", f"Unit tests pass for {n}", "The service resolves when the app starts"]
            elif cat == "wiring":
                title = f"Register {n} in {posixpath.basename(r.filePath)}"
                val = [f"Compiles: {build}", "The application starts without dependency-resolution errors",
                       f"Each of these resolves from the container: {n}"]
            elif cat == "controller":
                title = (f"Add controller exposing {n}" if r.action == "create"
                         else f"Add actions to existing controller ({posixpath.basename(r.filePath)}): {n}")
                val = [f"Compiles: {build}", *(f"{x} responds with the expected status and content" for x in names[:6]),
                       "Controller actions are covered by tests"]
            elif cat == "ui":
                title = f"Create {n} page" if sub == "page" else f"Add {n} view"
                val = ["It renders without console/server errors", "It can be reached through normal navigation",
                       "Content and layout match the enhancement's version"]
            else:  # routing
                title = f"Add route{'s' if len(names) > 1 else ''} {n} to {posixpath.basename(r.filePath)}"
                val = [*(f"{x} resolves to the intended component/action" for x in names[:6]),
                       "Existing routes still resolve (no path is shadowed)", "Navigation links to the new route work"]
            if conflicts:
                desc += " Conflicts to resolve first: " + "; ".join(c.removeprefix("Conflict: ") for c in conflicts[:3]) + "."
                val.append("Conflict decided with the owners of the affected data/contract and recorded in the PR")
            elif adds and r.action == "modify":
                desc += " Changes: " + "; ".join(adds[:3]) + "."
            out.append(_Task(category=cat, title=title, description=desc, files=files, validation=val, level=level))
        return out

    # ---- phase 3 ---------------------------------------------------
    def _verification_tasks(self, impact: ImpactAnalysisResult, items: List[AffectedItem],
                            stacks: Dict[str, bool]) -> List[_Task]:
        build, tasks = self._build(stacks), []
        existing = [i for i in items if i.change != "added"]
        risky = [i for i in existing if i.level in ("Medium", "High")
                 and i.category in ("controllers", "services", "components")]
        if risky:
            risky.sort(key=lambda i: -i.score)
            detail = "; ".join(f"{i.name} ({i.level}): {i.reasons[0] if i.reasons else ''}" for i in risky[:6])
            tasks.append(_Task(
                "verify", "Update and verify affected existing code",
                f"{len(risky)} existing item(s) depend on the changed code. {detail}.",
                sorted({i.file for i in risky if i.file}),
                [f"Compiles: {build}", f"Run the existing tests that cover: {_join([i.name for i in risky], 6)}",
                 "Fix call sites broken by changed signatures, types or contracts",
                 "Manually exercise the screens that use these items"],
                _max_level([i.level for i in risky])))
        exposed = [i for i in existing if i.category in ("routes", "apis")]
        if exposed:
            exposed.sort(key=lambda i: -i.score)
            tasks.append(_Task(
                "verify", "Regression-test affected routes and APIs",
                f"{len(exposed)} existing route/API(s) sit on code that changes; confirm they behave as before.",
                sorted({i.file for i in exposed if i.file}),
                [f"Request {i.name} and confirm status and response are unchanged" for i in exposed[:8]]
                + ["Compare against a baseline captured before the change"],
                _max_level([i.level for i in exposed])))
        added = [i for i in items if i.change == "added" and i.category in ("routes", "apis", "components")]
        if added:
            tasks.append(_Task(
                "verify", "Validate new functionality end to end",
                "Walk through every new route, API and page as a user would.",
                sorted({i.file for i in added if i.file}),
                [*(f"Use {i.name}: expected result is correct and error-free" for i in added[:8]),
                 "Check application logs for new errors or warnings"], "Low"))
        tasks.append(_Task(
            "verify", "Final build, full test run and release readiness",
            "Last gate before merge.", [],
            [f"Clean build: {build}", "Full automated test suite passes",
             "The diff contains only the files named in this plan", "README/docs updated if public behaviour changed"],
            impact.overallLevel))
        return tasks

    # ---- fallback when only the impact result is available ------
    @staticmethod
    def _derive(impact: ImpactAnalysisResult, items: List[AffectedItem]) -> List[RecommendedLocation]:
        kind_of = {"controllers": "controller", "services": "service", "routes": "route", "apis": "api"}
        recs = []
        for n, p in enumerate(impact.integrationPoints, 1):
            at = [i for i in items if p.filePath in i.integrationPoints]
            pick = [i for i in at if (i.change == "added") == (p.action == "create") and i.distance == 0]
            tags = []
            for i in pick:
                kind = kind_of.get(i.category) or ("page" if (i.file or "").endswith(JS_EXT) else "view")
                tags.append(f"{kind}:{i.name}")
            recs.append(RecommendedLocation(
                rank=n, filePath=p.filePath, locationType="directory" if p.filePath.endswith("/") else "file",
                action=p.action, reason=p.summary, confidence=0, supports=tags,
                suggestedFiles=sorted({i.file for i in pick if i.file}) if p.action == "create" else [],
                evidence=[p.summary] if "onflict" in p.summary else []))
        return recs

    # ---- rendering -------------------------------------------------
    @staticmethod
    def _markdown(plan: ImplementationPlan) -> str:
        lines = [f"# Implementation Plan: {plan.enhancementApplication} → {plan.baseApplication}", "",
                 f"Overall impact: **{plan.overallImpact}** ({plan.overallScore}/100)", "", plan.summary]
        for ph in plan.phases:
            lines += ["", f"## Phase {ph.number} – {ph.name}", "", f"_Goal: {ph.goal}_"]
            if not ph.tasks:
                lines += ["", "_No tasks in this phase._"]
            for t in ph.tasks:
                lines += ["", f"### Task {t.id[1:]}: {t.title}", f"Risk: {t.level} · Effort: {t.effort}", "",
                          f"**Description:** {t.description}", "", "**Files involved:**"]
                lines += [f"- `{f}`" for f in t.files] or ["- (none; repository-wide)"]
                lines += ["", "**Dependencies:** " + (", ".join(t.dependsOn) or "none"), "", "**Validation:**"]
                lines += [f"- [ ] {v}" for v in t.validation]
            lines += ["", "**Exit criteria:**"] + [f"- {c}" for c in ph.exitCriteria]
        if plan.warnings:
            lines += ["", "## Warnings", ""] + [f"- {w}" for w in plan.warnings]
        return "\n".join(lines) + "\n"
