"""
scenario_generator.py
---------------------
Stage: Testing/Validation
Generates "hostile" or malformed pipeline outputs for testing the Arbiter.
"""
import json
from src.config.prompts import load_skill_body, load_base_rules
from src.config.settings import AGENT_MODELS, AGENT_TEMPERATURES
from src.utils import LLMClient, extract_json

class ScenarioGenerator:
    """
    Generates variations of a 'Known Good' sample to test Arbiter judge's robustness.
    """
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.llm = LLMClient(run_id=run_id, agent_name="scenario_generator")

    def generate(self, pass_sample: dict) -> dict:
        """
        Take a valid pipeline output and transform it into a HOSTILE test case.
        
        Returns ScenarioOutput JSON:
            original_sample: dict
            modified_sample: dict
            injected_errors: list[{judge, severity, description}]
        """
        skill_body = load_skill_body("scenario_generator")
        base_rules = load_base_rules()
        system = f"<base_rules>\n{base_rules}\n</base_rules>\n\n{skill_body}"
        
        user = (
            "<input>\nPASS SAMPLE TO MODIFY:\n"
            + json.dumps(pass_sample, indent=2)
            + "\n</input>\n\nReturn your ScenarioOutput JSON now."
        )

        raw = self.llm.complete(
            system=system,
            user=user,
            model=AGENT_MODELS.get("scenario_generator", AGENT_MODELS["analyst"]),
            temperature=AGENT_TEMPERATURES.get("scenario_generator", 0.7),
        )
        return extract_json(raw)
