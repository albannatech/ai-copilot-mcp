# Changelog

All notable changes to AI Copilot MCP are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the app uses [semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

**`REQUIRES_CORE` bumped to `>=0.4.0,<0.5.0`.**

The core shipped 0.4.0 with four bug fixes and no contract change, and this
extension still declared `>=0.3.0,<0.4.0` — so updating the core would have
refused its activation. The gate was right and the declaration was stale.

The new bound is earned rather than asserted: this extension's tests import the
real core and run its manifest through the core's own validator, and they pass
against 0.4.0.
## [0.1.0] — 2026-11-12

### Added

**The flagship: the extension that makes a fresh install of the core useful.**

Eight tools, one agent, one doctype, no flow, and no HTTP client.

- `tools/manifest.py` — the contract. Imports no Frappe, so the core can
  validate it on a machine with none of this app's dependencies installed.
  `REQUIRES_CORE = ">=0.3.0,<0.4.0"`, the first core version whose authority
  layer applies `without_writes_out_of_reach` to extension specs as well as
  core ones.
- `tools/erpnext.py` — the Frappe handlers. They call Frappe directly, inside
  the request the chat already opened, so the authority layer sees the caller's
  real roles and permissions and `frappe.has_permission` answers per document.
- `agent.py` — persona, five boundaries, three prompts, and a deterministic
  `system_prompt()`.
- `hooks.py` — `frappe_mcp_tools`, `frappe_mcp_agent`, and no second chat
  surface.
- Doctypes: `AI Copilot MCP Settings`.
- `install.py` — creates the role and the Single settings row, idempotently.
  `core_has_builtin_query_tools` records the product decision as a *statement*,
  not a switch.
- `tests/test_manifest.py`, `tests/test_copilot.py` — 44 tests that import the
  **real core** and run this manifest through the core's own validator.

### The decisions it demonstrates

- **The tools run in-process, not over REST.** A server-side REST call runs as a
  service principal and sees Administrator's permissions; a browser-side
  `frappe.call` runs as the user but happens in the browser while the tool loop
  is server-side. You cannot have both, so there is no HTTP client here and a
  test asserts it.
- **This is an agent configuration, not a second chat surface.** The core ships
  the docked panel; this contributes the persona, the prompts and the tool set
  that panel runs when this agent is active. One runtime, one conversation
  store, many agents.
- **Ambiguity is resolved by asking.** "Overdue invoices over ten thousand"
  needs three answers before it has one. `ask_question` is tiered read because
  it changes no business data.
- **Every write names its `doctype_arg` and its `write_permission`.** Without
  both, the reach check cannot answer the target question and the tool would be
  visible to everyone.
- **The first-run question is answered explicitly.** The core ships chat and
  file tools only, so a fresh install cannot answer business questions until
  this extension is installed. That is recorded rather than left to look like a
  bug.

