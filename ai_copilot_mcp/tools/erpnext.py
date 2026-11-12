"""The Frappe handlers — the only module here that imports Frappe.

Eight tools, and the shape of each is dictated by one decision: **the tools run
in-process, under the caller's own Frappe session.**

The spec this extension was written from said *chat widget → LLM with
tool-calling → Frappe REST API*.  The REST hop is the defect, and it is worth
spelling out why, because it looks like the obvious design:

- A **server-side REST call** from the tool loop runs as a service principal and
  sees Administrator's permissions.  "Show overdue invoices" would show every
  user every invoice on the site.
- A **browser-side ``frappe.call``** runs as the user — but it happens in the
  *browser*, while the tool loop is *server-side*.  You cannot have both.

So the handlers call Frappe directly, inside the request the chat already
opened.  The authority layer sees the caller's real roles and permissions, and
``frappe.has_permission`` answers per document rather than per doctype.  That is
the whole of the security model, and it is why there is no HTTP client in this
file.

``ask_question`` is tiered ``read`` because it changes no business data.  What
it does write is a row of the app's own chat data — the same kind of thing the
assistant's own reply writes.
"""

from __future__ import annotations

from typing import Any

import frappe

from albanna_ai_chat.core.port import ToolContext, ToolResult
from albanna_ai_chat.core.tools import ToolSpec, compact_json, validate_arguments

SETTINGS_DOCTYPE = "AI Copilot MCP Settings"

TOOL_NAMES = frozenset(
    {
        "list_docs",
        "get_doc",
        "get_doctype_meta",
        "run_report",
        "ask_question",
        "create_doc",
        "update_doc",
        "delete_doc",
    }
)


class ERPNextBackend:
    """Runs this extension's eight tools, in-process, as the caller."""

    def handles(self, name: str) -> bool:
        return name in TOOL_NAMES

    def call(
        self,
        spec: ToolSpec,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        problem = validate_arguments(spec, arguments)
        if problem:
            return ToolResult.failure(problem, error="invalid_arguments")

        handler = getattr(self, f"_run_{spec.name}", None)
        if handler is None:  # pragma: no cover
            return ToolResult.failure(
                f"{spec.name} is not implemented.", error="not_implemented"
            )
        return handler(arguments, context)

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------

    def _run_list_docs(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        doctype = arguments["doctype"]
        if not frappe.has_permission(doctype, "read"):
            return ToolResult.refusal(
                f"This account may not read {doctype}.", error="denied"
            )

        rows = frappe.get_list(
            doctype,
            filters=list(arguments.get("filters") or []),
            fields=arguments.get("fields") or ["name"],
            limit_page_length=arguments.get("limit") or 20,
            order_by=arguments.get("order_by") or "modified desc",
        )
        return ToolResult.success(
            compact_json(rows), data=rows, summary=f"Found {len(rows)} {doctype}(s)"
        )

    def _run_get_doc(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        doctype, name = arguments["doctype"], arguments["name"]
        if not frappe.has_permission(doctype, "read", doc=name):
            return ToolResult.refusal(
                f"This account may not read {doctype}/{name}.", error="denied"
            )
        doc = frappe.get_doc(doctype, name)
        fields = arguments.get("fields")
        payload = (
            {f: doc.get(f) for f in fields}
            if fields
            else doc.as_dict()
        )
        return ToolResult.success(
            compact_json(payload), data=payload, summary=f"{doctype}/{name}"
        )

    def _run_get_doctype_meta(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        doctype = arguments["doctype"]
        if not frappe.has_permission(doctype, "read"):
            return ToolResult.refusal(
                f"This account may not read {doctype}.", error="denied"
            )
        meta = frappe.get_meta(doctype)
        wanted = arguments.get("fields")
        rows = [
            {
                "fieldname": f.fieldname,
                "fieldtype": f.fieldtype,
                "label": f.label,
                "reqd": f.reqd,
                "options": f.options,
            }
            for f in meta.fields
            if not wanted or f.fieldname in wanted
        ]
        return ToolResult.success(
            compact_json(rows), data=rows, summary=f"{len(rows)} field(s) on {doctype}"
        )

    def _run_run_report(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        report = arguments["report"]
        filters = arguments.get("filters") or {}
        try:
            result = frappe.desk.reportview.get_filtered_data(
                report, filters=filters, limit_page_length=arguments.get("limit") or 1000
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failure(
                f"The report {report!r} could not be run: {exc}", error="report_failed"
            )
        rows = result.get("result", []) if isinstance(result, dict) else result
        return ToolResult.success(
            compact_json(rows), data=rows, summary=f"{len(rows)} row(s) from {report}"
        )

    def _run_ask_question(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        # The question is written to the conversation, not to the site's
        # business data — which is why this tool is tiered read.
        if not context.conversation:
            return ToolResult.failure(
                "A question needs a conversation to be asked in.",
                error="no_conversation",
            )
        payload = {
            "question": arguments["question"],
            "options": arguments["options"],
            "multiple": bool(arguments.get("multiple")),
        }
        return ToolResult.success(
            compact_json(payload),
            data=payload,
            summary=f"Asked: {arguments['question'][:60]}",
        )

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------

    def _run_create_doc(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        doctype = arguments["doctype"]
        if not frappe.has_permission(doctype, "create"):
            return ToolResult.refusal(
                f"This account may not create {doctype}.", error="denied"
            )
        doc = frappe.get_doc({"doctype": doctype, **arguments["data"]})
        doc.insert()
        if arguments.get("submit") and doc.meta.is_submittable:
            doc.submit()
        return ToolResult.success(
            compact_json({"name": doc.name}),
            data={"name": doc.name},
            summary=f"Created {doctype}/{doc.name}",
        )

    def _run_update_doc(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        doctype, name = arguments["doctype"], arguments["name"]
        if not frappe.has_permission(doctype, "write", doc=name):
            return ToolResult.refusal(
                f"This account may not change {doctype}/{name}.", error="denied"
            )
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus == 1:
            # A submitted document cannot be edited.  It has to be cancelled
            # and amended, which this tool does not do — and saying so is the
            # correct answer rather than trying.
            return ToolResult.refusal(
                f"{doctype}/{name} is submitted and cannot be changed. It has to "
                "be cancelled and amended, which this tool does not do.",
                error="submitted",
            )
        for fieldname, value in arguments["data"].items():
            doc.set(fieldname, value)
        doc.save()
        return ToolResult.success(
            compact_json({"name": doc.name}),
            summary=f"Updated {doctype}/{name}",
        )

    def _run_delete_doc(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        doctype, name = arguments["doctype"], arguments["name"]
        if not frappe.has_permission(doctype, "delete", doc=name):
            return ToolResult.refusal(
                f"This account may not delete {doctype}/{name}.", error="denied"
            )
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus == 1:
            return ToolResult.refusal(
                f"{doctype}/{name} is submitted and must be cancelled first, "
                "which this tool does not do.",
                error="submitted",
            )
        frappe.delete_doc(doctype, name)
        return ToolResult.success(
            compact_json({"deleted": name}), summary=f"Deleted {doctype}/{name}"
        )


__all__ = ["ERPNextBackend"]
