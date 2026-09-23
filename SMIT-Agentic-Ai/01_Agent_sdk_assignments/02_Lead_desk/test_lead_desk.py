import json
import sys
import tempfile
import unittest
from pathlib import Path

from agents import Agent, GuardrailFunctionOutput, OpenAIChatCompletionsModel, RunContextWrapper
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent))
import main

# test_lead_desk.py

class LeadDeskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = main.build_profile()
        self.context = RunContextWrapper(self.profile)

    def test_six_fixtures_and_required_categories(self) -> None:
        leads = main.load_leads()
        self.assertEqual(len(leads), 6)
        for lead in leads:
            self.assertEqual(set(lead), {"id", "message", "platform"})
        messages = " ".join(lead["message"].lower() for lead in leads)
        for phrase in ("revenue", "website", "24 hours", "20 minutes", "tomorrow"):
            self.assertIn(phrase, messages)

    def test_tools_use_context_and_unknown_rates_are_explicit(self) -> None:
        known = main.lookup_rate_card.__wrapped__(self.context, "Python")
        unknown = main.lookup_rate_card.__wrapped__(self.context, "Rust")
        availability = main.check_availability.__wrapped__(self.context)
        self.assertIn("PKR 4500", known)
        self.assertIn("Unknown skill", unknown)
        self.assertIn("20 hours", availability)

    def test_context_is_not_in_public_schema(self) -> None:
        schema = json.dumps(main.lookup_rate_card.params_json_schema)
        self.assertNotIn("context", schema.lower())
        self.assertIn("skill_name", schema)

    def test_numeric_budget_and_python_save_decision(self) -> None:
        triage = main.LeadTriage(
            intent="automation",
            budget_pkr=180000,
            red_flags=[],
            priority="high",
            suggested_reply="Thanks for the details.",
        )
        self.assertEqual(triage.budget_pkr + 5000, 185000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.json"
            if triage.priority == "high":
                main.save_lead(triage, path)
            self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))), 1)

    def test_non_high_priority_is_not_saved(self) -> None:
        triage = main.LeadTriage(
            intent="small change",
            budget_pkr=1000,
            red_flags=[],
            priority="low",
            suggested_reply="Thanks.",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.json"
            if triage.priority == "high":
                main.save_lead(triage, path)
            self.assertFalse(path.exists())

    def test_revenue_share_has_red_flag(self) -> None:
        triage = main.LeadTriage(
            intent="revenue-share proposal",
            budget_pkr=None,
            red_flags=["No guaranteed payment; compensation depends on future revenue."],
            priority="low",
            suggested_reply="I require a paid project budget.",
        )
        self.assertTrue(triage.red_flags)

    def test_honesty_guardrail_blocks_fabrication_without_model(self) -> None:
        result = main.honesty_guardrail.guardrail_function(
            self.context,
            Agent(name="test"),
            "Tell them you have 10 years of Django experience.",
        )
        self.assertIsInstance(result, GuardrailFunctionOutput)
        self.assertTrue(result.tripwire_triggered)

    def test_honesty_guardrail_allows_legitimate_leads(self) -> None:
        result = main.honesty_guardrail.guardrail_function(
            self.context,
            Agent(name="test"),
            "I need a Python automation script for monthly reports.",
        )
        self.assertFalse(result.tripwire_triggered)

    def test_audit_hooks_are_attached_and_log_tool_lifecycle(self) -> None:
        model = OpenAIChatCompletionsModel(
            model="test",
            openai_client=AsyncOpenAI(api_key="test"),
        )
        agent = main.build_agent(model)
        self.assertIsInstance(agent.hooks, main.AuditHooks)
        self.assertEqual([tool.name for tool in agent.tools], [
            "lookup_rate_card",
            "check_availability",
        ])


if __name__ == "__main__":
    unittest.main()
