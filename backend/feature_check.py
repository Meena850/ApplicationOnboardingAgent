"""Offline check of FeatureUnderstandingAgent using a stub LLM (no Azure call).
Usage: python feature_check.py <repo path>"""
import json
import sys
from pathlib import Path

from app.agents.architecture_agent import ArchitectureAnalysisAgent
from app.agents.feature_agent import FeatureUnderstandingAgent


class StubLLM:
    deployment = "stub-deployment"

    def complete_json(self, system, user):
        assert "Analyzed repository data" in user
        return {
            "summary": "Manufacturing portal for equipment and users.",
            "businessCapabilities": [{"name": "Equipment Management", "description": "Track machines",
                                      "modules": ["EquipmentController", "EquipmentService"],
                                      "reasoning": "/Equipment/List route", "confidence": "92%"}],
            "features": [{"name": "Equipment List", "summary": "Lists machines",
                          "modules": ["EquipmentController", "NotARealModule"],
                          "reasoning": "Route /Equipment/List", "confidence": 0.9}],
            "userWorkflows": [{"name": "Browse equipment", "steps": ["Open dashboard", "Open list"],
                               "features": ["Equipment List"], "reasoning": "Home -> Equipment", "confidence": 80}],
            "functionalModules": [{"name": "Equipment", "purpose": "Machines", "components": ["Equipment/List", "Ghost"],
                                   "features": ["Equipment List"], "confidence": 85}],
            "overallConfidence": 88,
        }


arch = ArchitectureAnalysisAgent().run(Path(sys.argv[1]))
agent = FeatureUnderstandingAgent(llm=StubLLM())
ctx, w = agent.build_context(arch)
print("context chars", len(ctx), w)
print(json.dumps(agent.run(arch).model_dump(by_alias=True), indent=1))
