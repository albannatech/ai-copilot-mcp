# AI Copilot MCP

Natural-language queries over ERP data — **the reference extension for
in-process tools, an agent over the core's single chat surface, and ambiguity
resolved by asking.**

An extension to [`albanna-ai-chat`](https://github.com/albannatech/albanna-ai-chat).
Install the core first; this app contributes tools, an agent and prompts to it.

```bash
bench get-app https://github.com/albannatech/ai-copilot-mcp.git
bench --site {site} install-app ai_copilot_mcp
```

---

## The load-bearing decision

**The tools run in-process, under the caller's own Frappe session.**

The spec this extension was written from said *chat widget → LLM with
tool-calling → Frappe REST API*. The REST hop is the defect, and it looks like
the obvious design until you follow it through:

- A **server-side REST call** from the tool loop runs as a service principal and
  sees **Administrator's** permissions. "Show overdue invoices" would show every
  user every invoice on the site.
- A **browser-side `frappe.call`** runs as the user — but it happens in the
  *browser*, while the tool loop is *server-side*. You cannot have both.

So the handlers call Frappe directly, inside the request the chat already
opened. The authority layer sees the caller's real roles and permissions, and
`frappe.has_permission` answers per document rather than per doctype. **There is
no HTTP client in this extension**, and a test asserts it.

---

## The second decision

**This extension is an agent configuration, not a second chat surface.**

The core ships the docked panel — the frontend ported from `albanna`'s
side-chat, with its contract adapters rewritten. This app contributes the
persona, the prompts and the tool set that panel runs when this agent is active.
One runtime, one conversation store, many agents. There is no second widget and
no parallel conversation state.

---

## The third decision

**Ambiguity is resolved by asking, not guessing.**

"Show overdue invoices over ten thousand" needs three answers before it has one:
which company, which currency, and what "overdue" means — due date passed,
unpaid, or partially paid. `ask_question` puts the choice in front of the reader
and waits. A financial number produced by a guess is a liability.

`ask_question` is tiered **read**, because it changes no business data. What it
writes is a row of the app's own chat data — the same kind of thing the
assistant's own reply writes.

---

## The surface

Eight tools, no flow.

| Tool | Tier | Undone by |
|---|---|---|
| `list_docs` | read | — |
| `get_doc` | read | — |
| `get_doctype_meta` | read | — |
| `run_report` | read | — |
| `ask_question` | read | — |
| `create_doc` | write | `delete_doc` |
| `update_doc` | write | irreversible — says why |
| `delete_doc` | write | irreversible — says why |

Every write names the DocType it acts on (`doctype_arg`) and the permission it
is authorised against (`write_permission`) — without both, the reach check
cannot answer the target question and the tool would be visible to everyone.

---

## The product decision this forces

The core ships chat and file tools **and nothing else**. A fresh install cannot
answer "show me my invoices" until this extension is installed. That is
deliberate, and it is recorded in `AI Copilot MCP Settings` as
`core_has_builtin_query_tools` — a *statement*, not a switch — so the first-run
experience is explained rather than looking broken.

---

## Testing

```bash
python -m pytest tests/
```

44 tests. `test_copilot.py` asserts the flagship-specific decisions: the handlers
import Frappe directly and no HTTP client, no tool declares a URL, path or SQL
parameter, `ask_question` is tiered read with bounded options, and every write
names both its `doctype_arg` and its `write_permission`.

The core is expected at `../albanna-ai-chat`; see `pythonpath` in
`pyproject.toml`.

---

## Requires core

`>=0.3.0,<0.4.0` — the first core version whose authority layer applies
`without_writes_out_of_reach` to extension specs as well as core ones.
