"""What this extension contributes to the core — the whole contract.

An extension is a Frappe app that implements the ``frappe_mcp_tools`` hook.
This module is what that hook points at: ``TOOLS`` (a list of ``ToolSpec``)
and ``TIERS`` (every name classified).  The core validates both atomically and
absorbs them tagged with this app's name, so uninstalling removes exactly these
tools and nothing else.

Why the surface looks like this
-------------------------------
Eight tools, no flow.  This is the flagship: the extension that makes a fresh
install of the core useful, by giving the chat a way to answer *"show overdue
invoices over ten thousand"*.

The load-bearing decision is not in this file
---------------------------------------------
**The tools run in-process, under the caller's own Frappe session.**

The spec this extension was written from said *chat widget → LLM with
tool-calling → Frappe REST API*.  The REST hop is the defect.  A server-side
REST call from the tool loop runs as a service principal and sees
**Administrator's** permissions — so "show overdue invoices" would show every
user every invoice on the site.  The alternative, ``frappe.call`` from the
browser, runs as the user but happens in the *browser*, while the tool loop is
*server-side*.  You cannot have both.

So the handlers call Frappe directly, inside the request the chat already
opened, and the authority layer sees the caller's real roles and permissions.
That is the whole of the security model, and it is why this extension has no
HTTP client in it.

**Ambiguity is resolved by asking, not guessing.**  "Overdue" means four
different things; "> 10k" has three currencies.  ``ask_question`` puts the
choice in front of the reader and waits.  A financial number produced by a guess
is a liability.

Nothing here imports Frappe
---------------------------
The manifest is the contract, and the contract must be importable on a machine
with none of this app's dependencies installed — that is what lets the core
validate it before anything runs.  The handlers live in ``erpnext.py``.
"""

from __future__ import annotations

from albanna_ai_chat.core.flow import CompensationSpec
from albanna_ai_chat.core.tools import READ, WRITE, ToolSpec

#: The DocTypes this extension owns.  It owns none of the data it acts on —
#: that is the point of a copilot.  It owns only its own settings.
SETTINGS = "AI Copilot MCP Settings"


def _schema(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


_FILTERS = {
    "filters": {
        "type": "array",
        "description": (
            "Filter conditions, each one exactly three strings: "
            "[fieldname, operator, value]. Operators: =, !=, >, <, >=, <=, "
            "like, not like, in, not in, is, between. The value is always a "
            "plain string — for a date use YYYY-MM-DD, for a number use digits."
        ),
        "items": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        },
    }
}

_FIELDS = {
    "fields": {
        "type": "array",
        "description": "Fieldnames to return — the exact fieldnames, not labels.",
        "items": {"type": "string"},
    }
}


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

LIST_DOCS = ToolSpec(
    name="list_docs",
    description=(
        "Find documents of one DocType. Use this to answer 'what do I have' "
        "questions: which Sales Orders are open, which Items are low on stock, "
        "which Customers have a balance. Returns a compact list of matching "
        "documents. Always fetch the DocType schema with get_doctype_meta first "
        "if you are not certain which fields exist."
    ),
    parameters=_schema(
        {
            "doctype": {"type": "string", "description": "The DocType to search."},
            **_FILTERS,
            **_FIELDS,
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "description": "How many documents to return (default 20).",
            },
            "order_by": {"type": "string", "description": "Sort order."},
        },
        ["doctype"],
    ),
    tier=READ,
)

GET_DOC = ToolSpec(
    name="get_doc",
    description=(
        "Fetch one document by its DocType and name. Use this to read the "
        "detail behind a name you got from list_docs. Name the fields you need "
        "to keep the answer short — a full document can be very large."
    ),
    parameters=_schema(
        {
            "doctype": {"type": "string", "description": "The DocType."},
            "name": {"type": "string", "description": "The document's name."},
            **_FIELDS,
        },
        ["doctype", "name"],
    ),
    tier=READ,
)

GET_DOCTYPE_META = ToolSpec(
    name="get_doctype_meta",
    description=(
        "Get the field definitions of a DocType — fieldname, type, label, "
        "whether it is mandatory, and its options. Call this before you filter "
        "on or write to a field you are not certain about, so you use the real "
        "fieldname rather than a plausible guess."
    ),
    parameters=_schema(
        {
            "doctype": {"type": "string", "description": "The DocType to describe."},
            **_FIELDS,
        },
        ["doctype"],
    ),
    tier=READ,
)

RUN_REPORT = ToolSpec(
    name="run_report",
    description=(
        "Run an ERPNext report and return its rows. Use this for questions "
        "about totals and trends — receivables, stock balance, sales register — "
        "rather than reading documents one by one. Some reports require "
        "filters; if a filter is missing the tool says which one, and you "
        "should call it again with that filter added."
    ),
    parameters=_schema(
        {
            "report": {
                "type": "string",
                "description": "The report's name, exactly as ERPNext knows it.",
            },
            "filters": {
                "type": "object",
                "description": "Filter values for the report, as an object.",
                "additionalProperties": True,
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5000,
                "description": "How many rows to return (default 1000).",
            },
        },
        ["report"],
    ),
    tier=READ,
)

ASK_QUESTION = ToolSpec(
    name="ask_question",
    description=(
        "Ask the reader a question, and wait for their answer in the chat. Use "
        "this when the task cannot go on without a choice that only the reader "
        "can make — which company, which currency, what 'overdue' means, which "
        "of two ways. The reader is shown the question and the options as a "
        "list they choose from, and their choice comes back as their next "
        "message. Offer the exact values you would use as the option's value, "
        "and the readable name as its label. Do not answer it yourself and do "
        "not act on a guess: once you have asked, the turn ends and the reader "
        "decides."
    ),
    parameters=_schema(
        {
            "question": {
                "type": "string",
                "description": "The question, in the reader's own language.",
            },
            "options": {
                "type": "array",
                "description": "The answers the reader may choose from.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["label", "value"],
                },
                "minItems": 2,
                "maxItems": 50,
            },
            "multiple": {"type": "boolean", "default": False},
        },
        ["question", "options"],
    ),
    tier=READ,
)


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

CREATE_DOC = ToolSpec(
    name="create_doc",
    description=(
        "Create a document. Use this only when the user has asked for the "
        "document to be created — never to test that something works, and "
        "never on a guess. If a required field is missing, ask the user for it "
        "rather than inventing a value."
    ),
    parameters=_schema(
        {
            "doctype": {"type": "string", "description": "The DocType to create."},
            "data": {
                "type": "object",
                "description": "The document's field values, as an object.",
                "additionalProperties": True,
            },
            "submit": {"type": "boolean"},
        },
        ["doctype", "data"],
    ),
    tier=WRITE,
    doctype_arg="doctype",
    write_permission="create",
    compensation=CompensationSpec(mechanism="reverse", undo_with=("delete_doc",)),
)

UPDATE_DOC = ToolSpec(
    name="update_doc",
    description=(
        "Change the fields of a document that already exists. Use this when "
        "the user names a document and asks for something to be different. "
        "Give only the fields that should change; every other field is left "
        "exactly as it is. A submitted document cannot be edited this way — it "
        "has to be cancelled and amended, which this tool does not do. Say so "
        "rather than trying. Never change a field the user did not ask about, "
        "and never change a document the user did not name."
    ),
    parameters=_schema(
        {
            "doctype": {"type": "string"},
            "name": {"type": "string"},
            "data": {"type": "object", "additionalProperties": True},
        },
        ["doctype", "name", "data"],
    ),
    tier=WRITE,
    doctype_arg="doctype",
    write_permission="write",
    # Frappe's own version history records what changed; this tool keeps no
    # separate copy, and saying so is more honest than implying an undo exists.
    compensation=CompensationSpec(
        mechanism="none",
        reason=(
            "An update overwrites the prior values, which this tool does not "
            "record separately. Frappe's own version history is the record of "
            "what changed."
        ),
    ),
)

DELETE_DOC = ToolSpec(
    name="delete_doc",
    description=(
        "Delete a document. Use this only when the user has explicitly asked "
        "for the document to be deleted. Only a draft or a cancelled document "
        "can be deleted; a submitted one must be cancelled first, which this "
        "tool does not do. Say so rather than trying. Deletion cannot be undone "
        "from here."
    ),
    parameters=_schema(
        {
            "doctype": {"type": "string"},
            "name": {"type": "string"},
        },
        ["doctype", "name"],
    ),
    tier=WRITE,
    doctype_arg="doctype",
    write_permission="delete",
    compensation=CompensationSpec(
        mechanism="none",
        reason=(
            "A deleted document is not recoverable from here. The operator "
            "holds a site backup; this tool does not."
        ),
    ),
)


#: Every tool this extension contributes.
TOOLS = [
    LIST_DOCS,
    GET_DOC,
    GET_DOCTYPE_META,
    RUN_REPORT,
    ASK_QUESTION,
    CREATE_DOC,
    UPDATE_DOC,
    DELETE_DOC,
]

#: Every tool classified.  The validator refuses a tool that is not here, so
#: this dict and TOOLS are kept in step by a test rather than by memory.
TIERS = {
    "list_docs": READ,
    "get_doc": READ,
    "get_doctype_meta": READ,
    "run_report": READ,
    "ask_question": READ,
    "create_doc": WRITE,
    "update_doc": WRITE,
    "delete_doc": WRITE,
}

#: The core version range this extension is built against.
#:
#: ``0.3.0`` is the first core version whose authority layer applies
#: ``without_writes_out_of_reach`` to extension specs as well as core ones.
#: An earlier core would show a write tool to a caller who held no such right
#: anywhere, which is the visibility rule broken.
REQUIRES_CORE = ">=0.4.0,<0.5.0"
