"""React scenario for IntegrationRecommendationAgent: base has a reports module; the enhancement adds a
report dashboard page + route. Usage: python recommend_react_check.py"""
import json
import shutil
import tempfile
from pathlib import Path

from app.agents.recommendation_agent import IntegrationRecommendationAgent

root = Path(tempfile.mkdtemp())


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


PKG = '{"name": "portal", "dependencies": {"react": "^18", "react-router-dom": "^6"}}'
APP = ('import {Route, Routes} from "react-router-dom";\n'
       'export default function App() { return (<Routes>\n'
       '  <Route path="/" element={<HomePage />} />\n'
       '  <Route path="/reports" element={<ReportList />} />\n'
       '  {EXTRA}</Routes>); }\n')
page = lambda n: f"export default function {n}() {{ return <div>{n}</div>; }}\n"

base, enh = root / "base", root / "enh"
for r, extra, pages in ((base, "", {}), (enh, '<Route path="/reports/dashboard" element={<ReportDashboard />} />\n',
                                       {"src/pages/reports/ReportDashboard.tsx": "ReportDashboard"})):
    write(r / "package.json", PKG)
    write(r / "src/App.tsx", APP.replace("{EXTRA}", extra))
    for f, n in {"src/pages/HomePage.tsx": "HomePage", "src/pages/Settings.tsx": "Settings",
                 "src/pages/reports/ReportList.tsx": "ReportList",
                 "src/pages/reports/ReportDetails.tsx": "ReportDetails", **pages}.items():
        write(r / f, page(n))

res = IntegrationRecommendationAgent().analyze_and_recommend(base, enh)
for rec in res.recommendations:
    print(f"Recommendation #{rec.rank}\nFile: {rec.filePath} ({rec.action})\nReason: {rec.reason}\n"
          f"Confidence: {rec.confidenceLabel}")
    for e in rec.evidence:
        print("  -", e)
    print()
print("considered", res.locationsConsidered, res.warnings)
shutil.rmtree(root, ignore_errors=True)
