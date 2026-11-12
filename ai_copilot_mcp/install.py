"""The installer — what has to exist before this extension is usable.

Two things, both idempotent, because a restored site repairs itself on the next
migrate rather than failing on a missing document the first time somebody opens
the widget.

The role is the load-bearing half.  ``AI Copilot MCP User`` is the gate: an
account may use these tools when it holds that role.  Creating it here rather
than in a fixture means a site restored from a backup gets it back.

The settings row records the product decision this extension forces
-------------------------------------------------------------------
``core_has_builtin_query_tools`` is a *statement*, not a switch.  The core ships
chat and file tools and nothing else, so a fresh install cannot answer "show me
my invoices" until this extension is installed.  That is a deliberate product
decision and it is written down here rather than left to whichever
implementation landed first — the alternative is a chat that looks broken on
first run and nobody knows why.
"""

from __future__ import annotations

import frappe

CORE_APP = "albanna_ai_chat"
ROLE = "AI Copilot MCP User"
SETTINGS = "AI Copilot MCP Settings"


def after_install() -> None:
    _require_core()
    _ensure_role()
    _ensure_settings()


def after_migrate() -> None:
    """Called on every migrate, so a restored site repairs itself."""
    _require_core()
    _ensure_role()
    _ensure_settings()


def _ensure_role() -> None:
    if frappe.db.exists("Role", ROLE):
        return
    frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(
        ignore_permissions=True
    )


def _ensure_settings() -> None:
    """The Single settings row.

    ``default_agent`` names the agent a new conversation starts with.  One
    active agent per conversation, chosen here and switchable mid-thread with
    the switch recorded.
    """
    if frappe.db.exists(SETTINGS, SETTINGS):
        return
    frappe.get_doc(
        {
            "doctype": SETTINGS,
            "default_agent": "ai_copilot",
            # A statement of the product decision, not a switch.  See the
            # module docstring.
            "core_has_builtin_query_tools": 0,
            # The most rows one report returns before the reader is told to
            # narrow it.
            "max_report_rows": 1000,
        }
    ).insert(ignore_permissions=True)


def _require_core() -> None:
    """Refuse to install without the core, and say which app to install.

    A raised exception here fails the install, which is correct: an extension
    whose tools cannot be discovered is not an extension, it is a directory.
    """
    if CORE_APP in frappe.get_installed_apps():
        return
    frappe.throw(
        f"This extension requires the frappe-mcp core. Install it first: "
        f"bench get-app https://github.com/albannatech/albanna-ai-chat.git "
        f"&& bench --site {{site}} install-app {{CORE_APP}}",
        title="Missing required app",
    )
