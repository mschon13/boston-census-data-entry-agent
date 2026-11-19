"""Agent orchestration for the Boston Census Data Entry prototype."""

from __future__ import annotations

from typing import Any

from tools import export_record, extract_fields, validate_record


class CensusEntryAgent:
    """A small tool-using agent with an explicit loop and audit trail."""

    def __init__(self, max_steps: int = 3):
        self.max_steps = max_steps

    def run(self, form_text: str) -> dict[str, Any]:
        audit = []
        record: dict[str, Any] = {}
        issues: list[dict[str, str]] = []

        for step in range(1, self.max_steps + 1):
            if not record:
                record = extract_fields(form_text)
                audit.append({"step": step, "tool": "extract_fields", "result": "Fields extracted"})

            issues = validate_record(record)
            audit.append({"step": step, "tool": "validate_record", "result": f"{len(issues)} issue(s) found"})

            blocking = [issue for issue in issues if issue["severity"] == "error"]
            if not blocking:
                status = "ready_for_review" if issues else "approved"
                audit.append({"step": step, "tool": "export_record", "result": status})
                return {"status": status, "record": export_record(record), "issues": issues, "audit": audit}

            # A production version could use an LLM or OCR re-read here. The
            # prototype stops safely instead of guessing when errors are blocking.
            audit.append({"step": step, "tool": "human_review_queue", "result": "Blocking issue requires review"})
            return {"status": "needs_review", "record": export_record(record), "issues": issues, "audit": audit}

        return {"status": "needs_review", "record": export_record(record), "issues": issues, "audit": audit}

