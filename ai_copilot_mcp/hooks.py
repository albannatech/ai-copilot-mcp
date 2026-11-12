"""Frappe app hooks — the one file Frappe reads to wire this app in.

This app is an *extension* to the frappe-mcp core.  It contributes tools, an
agent and prompts, and it is installed and uninstalled like any other Frappe
app — which is the whole point of using a Frappe hook rather than a Python
entry point.

The one line that matters
-------------------------
``frappe_mcp_tools`` points at this app's manifest module.  The core resolves
that hook **per site**, validates it atomically, and absorbs the tools tagged
with this app's name.  Install this app and the chat gains an ERP copilot;
uninstall it and those tools are gone, and only those tools.

Why not a Python entry point
----------------------------
An entry point lives in the bench *virtualenv*, which every site on the bench
shares.  Install this extension there and its tools appear on every site
running the core — including sites that do not have this app installed, where
``AI Copilot MCP Settings`` does not exist.  A Frappe hook is site-scoped, and
the scoping comes for free.

This extension is an agent configuration, not a second chat surface
--------------------------------------------------------------------
The core ships the docked panel — that is the frontend, ported from `albanna`'s
side-chat with its contract adapters rewritten.  This app contributes the
persona, the prompts and the tool set that panel runs when this agent is
active.  One runtime, one conversation store, many agents.  There is no second
widget here, and there is no parallel conversation state.
"""

app_name = "ai_copilot_mcp"
app_title = "AI Copilot MCP"
app_publisher = "Albanna Software Solutions"
app_description = (
    "Natural-language queries over ERP data — the reference extension for "
    "in-process tools, an agent over the core's single chat surface, and "
    "ambiguity resolved by asking."
)
app_email = "ahmedalbanna966@gmail.com"
app_license = "mit"


# --------------------------------------------------------------------------
# The extension seam.
#
# The value is a dotted path to a module carrying TOOLS and TIERS.  The core
# imports it, validates it atomically, and absorbs it.
# --------------------------------------------------------------------------

frappe_mcp_tools = "ai_copilot_mcp.tools.manifest"

# --------------------------------------------------------------------------
# The agent this extension brings.
#
# The core's prompt assembler reads this to build the system prompt when this
# extension's agent is the active one.  Pure data, so it is testable without
# a site.
# --------------------------------------------------------------------------

frappe_mcp_agent = "ai_copilot_mcp.agent"

# The installer creates the Single settings row and the role, so the extension
# is usable and configurable the moment it is installed.
after_install = "ai_copilot_mcp.install.after_install"
after_migrate = "ai_copilot_mcp.install.after_migrate"
