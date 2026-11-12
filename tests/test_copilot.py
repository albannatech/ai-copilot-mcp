"""The flagship-specific half: in-process, and ambiguity resolved by asking.

The failure these guard against is not a crash — it is a tool loop that hops
over REST and answers as Administrator, or a financial number produced by a
guess.
"""

import pytest

from ai_copilot_mcp.agent import AI_COPILOT_AGENT
from ai_copilot_mcp.tools import manifest


# ---------------------------------------------------------------------------
# The tools run in-process
# ---------------------------------------------------------------------------


class TestInProcess:
    def test_the_handlers_import_frappe_directly(self):
        # Not a client, not a proxy — Frappe itself, inside the request the
        # chat already opened.
        import inspect

        from ai_copilot_mcp.tools import erpnext

        assert "import frappe" in inspect.getsource(erpnext)

    def test_no_tool_declares_a_url_parameter(self):
        # A URL parameter is how a tool becomes a remote call.
        for spec in manifest.TOOLS:
            assert "url" not in spec.parameters.get("properties", {}), spec.name

    def test_no_tool_declares_a_path_parameter(self):
        for spec in manifest.TOOLS:
            assert "path" not in spec.parameters.get("properties", {}), spec.name

    def test_no_tool_declares_a_sql_parameter(self):
        for spec in manifest.TOOLS:
            properties = spec.parameters.get("properties", {})
            for forbidden in ("sql", "query", "statement"):
                assert forbidden not in properties, f"{spec.name} has {forbidden}"


# ---------------------------------------------------------------------------
# Ambiguity is resolved by asking
# ---------------------------------------------------------------------------


class TestAmbiguityIsResolvedByAsking:
    def test_there_is_a_question_tool(self):
        assert "ask_question" in {s.name for s in manifest.TOOLS}

    def test_the_question_tool_is_tiered_read(self):
        # It changes no business data.  What it writes is a row of the app's
        # own chat data, the same kind the assistant's reply writes.
        spec = next(s for s in manifest.TOOLS if s.name == "ask_question")
        assert spec.tier == "read"
        assert spec.mutating is False

    def test_the_question_tool_requires_at_least_two_options(self):
        spec = next(s for s in manifest.TOOLS if s.name == "ask_question")
        options = spec.parameters["properties"]["options"]
        assert options["minItems"] == 2

    def test_the_question_tool_caps_its_options(self):
        spec = next(s for s in manifest.TOOLS if s.name == "ask_question")
        options = spec.parameters["properties"]["options"]
        assert options["maxItems"] == 50

    def test_the_querying_prompt_names_the_ambiguities_it_must_ask_about(self):
        prompt = AI_COPILOT_AGENT.for_situation("querying")
        assert len(prompt) == 1
        text = prompt[0].text.lower()
        assert "which company" in text
        assert "which currency" in text
        assert "overdue" in text

    def test_the_boundary_forbids_guessing(self):
        joined = " ".join(AI_COPILOT_AGENT.boundaries).lower()
        assert "never guess" in joined


# ---------------------------------------------------------------------------
# The write path refuses what it must
# ---------------------------------------------------------------------------


class TestTheWritePath:
    def test_update_doc_says_a_submitted_document_cannot_be_changed(self):
        spec = next(s for s in manifest.TOOLS if s.name == "update_doc")
        assert "cancelled and amended" in spec.description

    def test_delete_doc_says_a_submitted_document_must_be_cancelled_first(self):
        spec = next(s for s in manifest.TOOLS if s.name == "delete_doc")
        assert "cancelled first" in spec.description

    def test_create_doc_says_never_to_test_or_guess(self):
        spec = next(s for s in manifest.TOOLS if s.name == "create_doc")
        assert "never to test" in spec.description
        assert "never on a guess" in spec.description

    def test_every_write_names_the_doctype_it_acts_on(self):
        # Without doctype_arg the reach check cannot answer the target
        # question, and the tool would be visible to everyone.
        for spec in manifest.TOOLS:
            if spec.mutating:
                assert spec.doctype_arg, spec.name

    def test_every_write_names_the_permission_it_is_authorised_against(self):
        for spec in manifest.TOOLS:
            if spec.mutating:
                assert spec.write_permission, spec.name


# ---------------------------------------------------------------------------
# The reads are bounded
# ---------------------------------------------------------------------------


class TestTheReadsAreBounded:
    def test_list_docs_caps_its_limit(self):
        spec = next(s for s in manifest.TOOLS if s.name == "list_docs")
        assert spec.parameters["properties"]["limit"]["maximum"] == 200

    def test_run_report_caps_its_limit(self):
        spec = next(s for s in manifest.TOOLS if s.name == "run_report")
        assert spec.parameters["properties"]["limit"]["maximum"] == 5000

    def test_get_doc_tells_the_model_to_name_the_fields_it_needs(self):
        spec = next(s for s in manifest.TOOLS if s.name == "get_doc")
        assert "keep the answer short" in spec.description

    def test_no_tool_accepts_unknown_arguments(self):
        # additionalProperties: false is enforced before a call is ever made.
        for spec in manifest.TOOLS:
            assert spec.parameters.get("additionalProperties") is False, spec.name
