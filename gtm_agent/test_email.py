import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "LANGSMITH_TRACING": "false"}):
    from gtm_agent.gtm_agent import send_prospect_email

from gtm_agent import data_service


class SendProspectEmailTests(unittest.TestCase):
    def setUp(self):
        self.runtime = SimpleNamespace(config={"metadata": {}})
        self.rep = {"name": "Sales Rep", "email": "rep@example.com"}
        self.prospect = {
            "prospect_id": "test-prospect",
            "name": "Prospect",
            "email": "prospect@example.com",
        }

    def send(self, prospect):
        return send_prospect_email.func(
            prospect, "Pricing", "Let's meet.", self.runtime, self.rep
        )

    def test_disqualified_source_blocks_even_if_caller_omits_or_changes_flag(self):
        with patch.dict(data_service.PROSPECTS, {
            "test-prospect": {**self.prospect, "disqualified": True}
        }):
            for flag in (None, False, True):
                with self.subTest(flag=flag):
                    prospect = dict(self.prospect)
                    if flag is not None:
                        prospect["disqualified"] = flag
                    result = self.send(prospect)
                    self.assertEqual(result["status"], "blocked_disqualified")
                    self.assertIn("disqualified", result["error"])
                    self.assertNotIn("message_id", result)

    def test_qualified_source_preserves_email_contents(self):
        with patch.dict(data_service.PROSPECTS, {
            "test-prospect": {**self.prospect, "disqualified": False}
        }):
            result = self.send({**self.prospect, "disqualified": True})
        self.assertEqual(result["status"], "sent")
        self.assertTrue(result["message_id"].startswith("msg-"))
        self.assertEqual(result["to"], self.prospect["email"])
        self.assertEqual(result["from"], self.rep["email"])
        self.assertEqual(result["subject"], "Pricing")
        self.assertEqual(result["body"], "Let's meet.")

    def test_missing_source_cannot_bypass_check(self):
        for prospect in ({"email": "prospect@example.com"}, self.prospect):
            with self.subTest(prospect=prospect):
                result = self.send(prospect)
                self.assertEqual(result["status"], "failed")
                self.assertNotIn("message_id", result)

    def test_qualified_prospect_without_email_still_fails(self):
        with patch.dict(data_service.PROSPECTS, {
            "test-prospect": {**self.prospect, "disqualified": False}
        }):
            result = self.send({"prospect_id": "test-prospect"})
        self.assertEqual(result["status"], "failed")
        self.assertIn("no email address", result["error"])
