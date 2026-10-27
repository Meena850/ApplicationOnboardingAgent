"""Run the architecture agent in-process. Usage: python arch_check.py <repo path>"""
import json
import sys
from pathlib import Path

from app.agents.architecture_agent import ArchitectureAnalysisAgent

r = ArchitectureAnalysisAgent().run(Path(sys.argv[1])).model_dump(by_alias=True)
print("summary", r["summary"], "warnings", r["warnings"])
print("modules", [(n["name"], n["fileCount"], {k: len(v) for k, v in n["layers"].items()}) for n in r["moduleMap"]["nodes"]])
print("module edges", r["moduleMap"]["edges"])
print("routes", [(x["path"], x["handler"], x["view"]) for x in r["routeMap"]["routes"]])
print("endpoints", [(e["method"], e["route"]) for e in r["apiMap"]["endpoints"]])
print("client calls", [(c["method"], c["route"], c["matchedEndpoint"]) for c in r["apiMap"]["clientCalls"]])
print("registrations", [(g["service"], g["implementation"], g["lifetime"]) for g in r["dependencyMap"]["registrations"]])
print("internal", [(e["source"], e["target"], e["via"]) for e in r["dependencyMap"]["internal"]][:25])
print("pkg usage", r["dependencyMap"]["packageUsage"])
