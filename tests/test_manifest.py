"""The extension contract, validated against the real core.

These tests import ``albanna_ai_chat`` — the core — and run this extension's
manifest through the core's own validator.  The flagship-specific half is in
``test_copilot.py``; this file is the contract.
"""

import pathlib
import sys
import types

import pytest

CORE = pathlib.Path(__file__).resolve().parent.parent.parent / "albanna-ai-chat"
if CORE.is_dir() and str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

albanna_ai_chat = pytest.importorskip("albanna_ai_chat")

from albanna_ai_chat.core.file_tools import CORE_TOOLS  # noqa: E402
from albanna_ai_chat.core.flow import MECHANISMS  # noqa: E402
from albanna_ai_chat.core.jobs import provider_imports  # noqa: E402
from albanna_ai_chat.core.tools import READ, WRITE  # noqa: E402
from albanna_ai_chat.core.validate import (  # noqa: E402
    ContractViolation,
    absorb,
    validate_module,
)

from ai_copilot_mcp.agent import AI_COPILOT_AGENT, system_prompt  # noqa: E402
from ai_copilot_mcp.tools import manifest  # noqa: E402


def module():
    mod = types.ModuleType("ai_copilot_mcp.tools.manifest")
    mod.TOOLS = manifest.TOOLS
    mod.TIERS = manifest.TIERS
    return mod


@pytest.fixture(scope="module")
def specs():
    return validate_module(module(), known_tools=set(CORE_TOOLS.names()))


@pytest.fixture(scope="module")
def registry(specs):
    from dataclasses import replace

    tagged = [replace(spec, source="ai_copilot_mcp") for spec in specs]
    return absorb(tagged, CORE_TOOLS)


class TestTheContractValidates:
    def test_the_core_accepts_every_tool(self, specs):
        assert len(specs) == len(manifest.TOOLS)

    def test_every_tool_is_classified(self, specs):
        for spec in specs:
            assert spec.tier in (READ, WRITE), spec.name

    def test_tiers_and_tools_agree(self, specs):
        assert {s.name for s in specs} == set(manifest.TIERS)

    def test_no_tool_shadows_a_core_tool(self, specs):
        assert not ({s.name for s in specs} & set(CORE_TOOLS.names()))

    def test_absorption_is_atomic_and_returns_a_new_registry(self, registry):
        assert len(registry) == len(CORE_TOOLS) + len(manifest.TOOLS)
        assert len(CORE_TOOLS) == 3, "the core's own surface must not have grown"


class TestProvenance:
    def test_every_tool_is_tagged_with_this_app(self, registry):
        assert [s.name for s in registry.from_source("ai_copilot_mcp")] == [
            s.name for s in manifest.TOOLS
        ]

    def test_uninstalling_removes_exactly_these_tools(self, registry):
        from albanna_ai_chat.core.toolset import without_source

        remaining = without_source(registry, "ai_copilot_mcp")
        assert set(remaining.names()) == set(CORE_TOOLS.names())


class TestCompensation:
    def test_every_write_declares_one(self, specs):
        for spec in specs:
            if spec.mutating:
                assert spec.compensation is not None, spec.name

    def test_every_mechanism_is_one_the_core_knows(self, specs):
        for spec in specs:
            if spec.compensation:
                assert spec.compensation.mechanism in MECHANISMS, spec.name

    def test_an_irreversible_action_says_why(self, specs):
        for spec in specs:
            if spec.compensation and spec.compensation.mechanism == "none":
                assert spec.compensation.reason.strip(), spec.name

    def test_the_undo_tools_actually_exist(self, specs, registry):
        for spec in specs:
            if not spec.compensation:
                continue
            for undo in spec.compensation.undo_with:
                assert undo in registry, f"{spec.name} names {undo}, which is not a tool"


class TestNoFlow:
    def test_there_are_no_flows(self, specs):
        assert [s.name for s in specs if s.is_flow] == []


class TestRequiresCore:
    def test_it_declares_one(self):
        assert manifest.REQUIRES_CORE

    def test_the_lower_bound_is_at_least_the_first_core_whose_authority_covers_extensions(self):
        # 0.3.0 is where without_writes_out_of_reach began applying to
        # extension specs as well as core ones.  The bound moves up as the core
        # does; what must not happen is a bound *below* the first core that can
        # load this extension.
        lower = manifest.REQUIRES_CORE.split(",")[0].lstrip(">=").strip()
        assert tuple(int(p) for p in lower.split(".")) >= (0, 3, 0), (
            f"lower bound {lower} is below the first core whose authority layer "
            "covers extension specs"
        )

    def test_the_upper_bound_pins_the_minor(self):
        # Pre-1.0, pinning to the minor is the honest declaration: a pre-1.0
        # core may change any part of its contract in a minor release.
        upper = manifest.REQUIRES_CORE.split(",")[-1].lstrip("<").strip()
        parts = upper.split(".")
        assert len(parts) == 3 and parts[2] == "0", (
            f"upper bound {upper} does not pin the minor — a pre-1.0 core may "
            "change its contract in a minor release, so the bound must fall on "
            "a minor boundary"
        )


class TestHookProhibition:
    def test_the_handlers_import_no_provider(self):
        import inspect

        from ai_copilot_mcp.tools import erpnext

        assert provider_imports(inspect.getsource(erpnext)) == []

    def test_the_handlers_import_no_http_client(self):
        # The tools run in-process.  An HTTP client here would mean a REST hop,
        # and a REST hop means a service principal with Administrator's rights.
        import inspect

        from ai_copilot_mcp.tools import erpnext

        source = inspect.getsource(erpnext)
        for client in ("requests", "httpx", "urllib.request"):
            assert f"import {client}" not in source, (
                f"{client} would mean a REST hop — the tools must run in-process"
            )


class TestTheAgent:
    def test_it_states_it_never_guesses_an_ambiguous_term(self):
        joined = " ".join(AI_COPILOT_AGENT.boundaries).lower()
        assert "never guess an ambiguous term" in joined

    def test_it_states_it_never_changes_a_submitted_document(self):
        joined = " ".join(AI_COPILOT_AGENT.boundaries).lower()
        assert "submitted document" in joined

    def test_it_states_it_never_invents_a_value(self):
        joined = " ".join(AI_COPILOT_AGENT.boundaries).lower()
        assert "never invent a value" in joined

    def test_the_system_prompt_is_deterministic(self):
        assert system_prompt("querying") == system_prompt("querying")

    def test_the_system_prompt_carries_the_boundaries(self):
        prompt = system_prompt()
        for boundary in AI_COPILOT_AGENT.boundaries:
            assert boundary in prompt

    def test_the_querying_prompt_names_the_three_ambiguities(self):
        prompt = system_prompt("querying").lower()
        assert "which company" in prompt
        assert "which currency" in prompt
        assert "overdue" in prompt


class TestTheValidatorRefuses:
    def test_an_unclassified_tool(self):
        from albanna_ai_chat.core.tools import ToolSpec

        mod = types.ModuleType("broken")
        mod.TOOLS = [
            ToolSpec(name="x", description="d", parameters={"type": "object", "properties": {}})
        ]
        mod.TIERS = {}
        with pytest.raises(ContractViolation):
            validate_module(mod, known_tools=set(CORE_TOOLS.names()))

    def test_a_sql_parameter(self):
        from albanna_ai_chat.core.tools import ToolSpec

        mod = types.ModuleType("broken")
        mod.TOOLS = [
            ToolSpec(
                name="run_sql",
                description="d",
                parameters={"type": "object", "properties": {"sql": {"type": "string"}}},
                tier=READ,
            )
        ]
        mod.TIERS = {"run_sql": READ}
        with pytest.raises(ContractViolation):
            validate_module(mod, known_tools=set(CORE_TOOLS.names()))
