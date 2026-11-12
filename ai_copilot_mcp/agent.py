"""The agent this extension brings, and the prompts it brings with it.

An extension is not only tools.  Every repo in this portfolio carries its own
tools, permissions, configurations, *agent* and *prompts* — and the agent is
what makes a set of tools into something with a point of view.  A chat with
eight ERP tools and no agent is a chat that will guess a currency to finish a
sentence.

This module is pure data.  It is Frappe-free so it can be tested without a
site, and so the core can assemble a system prompt from it without importing
anything this extension depends on.

How the core uses it
--------------------
The core's prompt assembler is deterministic and ordered: the core's own system
prompt, then the *active* extension's agent persona, then its task prompts,
then the conversation.  One active agent per conversation, chosen in Settings
and switchable mid-thread with the switch recorded.  Twenty extensions
contribute *content*; none of them contributes assembly logic.

**This extension is an agent configuration, not a second chat surface.**  The
core ships the docked panel; this contributes the persona, the prompts and the
tool set that panel runs when this agent is active.  One runtime, one
conversation store, many agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: This extension's name, as the core knows it.  It is the app name, because
#: that is what provenance is tagged with and what an uninstall keys on.
EXTENSION_NAME = "ai_copilot_mcp"


@dataclass(frozen=True)
class Prompt:
    """One instruction the agent is given."""

    name: str
    text: str
    when: str = ""


@dataclass(frozen=True)
class Agent:
    """What this extension contributes to a conversation's point of view."""

    name: str
    persona: str
    boundaries: tuple[str, ...] = ()
    prompts: tuple[Prompt, ...] = field(default_factory=tuple)

    def always_on(self) -> tuple[Prompt, ...]:
        return tuple(p for p in self.prompts if not p.when)

    def for_situation(self, situation: str) -> tuple[Prompt, ...]:
        return tuple(p for p in self.prompts if p.when == situation)


AI_COPILOT_AGENT = Agent(
    name="ai_copilot",
    persona=(
        "You answer questions about this site's business data and act on it "
        "when asked. You are careful about money and dates, because a figure "
        "that is wrong by a factor of ten looks exactly like one that is "
        "right. You ask rather than guess, and you say when something is "
        "outside what you can see."
    ),
    boundaries=(
        "Never guess an ambiguous term. 'Overdue' has four meanings and '> 10k' "
        "has three currencies — ask which one, with ask_question.",
        "Never act on a document the user did not name, and never change a "
        "field they did not ask about.",
        "Never change a submitted document. It has to be cancelled and "
        "amended, which these tools do not do.",
        "Never invent a value to fill a required field. Ask for it.",
        "Never report a number you did not read from the site. If a report "
        "needs a filter, say which one rather than assuming it.",
    ),
    prompts=(
        Prompt(
            name="querying",
            text=(
                "Before you answer a question about totals, check whether the "
                "question is ambiguous. 'Overdue invoices over ten thousand' "
                "needs three answers before it has one: which company, which "
                "currency, and what 'overdue' means — due date passed, unpaid, "
                "or partially paid. Ask with ask_question, offering the exact "
                "values you would use. A confident wrong number is worse than "
                "a question."
            ),
            when="querying",
        ),
        Prompt(
            name="writing",
            text=(
                "Before you create or change a document, read it back with "
                "get_doc and show the reader what you are about to write. A "
                "write the reader did not see is a write they cannot catch."
            ),
            when="writing",
        ),
        Prompt(
            name="reporting",
            text=(
                "When you report a figure, say where it came from — which "
                "report, which filters, how many rows. A number with no "
                "provenance is a number nobody can check."
            ),
            when="reporting",
        ),
    ),
)


def system_prompt(situation: str = "") -> str:
    """The system prompt for this agent, deterministically assembled."""
    parts = [AI_COPILOT_AGENT.persona]

    if AI_COPILOT_AGENT.boundaries:
        parts.append("You will not:")
        parts.extend(f"- {b}" for b in AI_COPILOT_AGENT.boundaries)

    for prompt in AI_COPILOT_AGENT.always_on():
        parts.append(prompt.text)

    if situation:
        for prompt in AI_COPILOT_AGENT.for_situation(situation):
            parts.append(prompt.text)

    return "\n\n".join(parts)
