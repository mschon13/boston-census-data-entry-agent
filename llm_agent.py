"""Optional live LLM agent using the OpenAI Responses API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from tools import export_record, extract_fields, validate_record


TOOLS = [
    {"type": "function", "name": "extract_fields", "description": "Extract census fields from the submitted form.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"type": "function", "name": "validate_record", "description": "Validate the currently extracted census record.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"type": "function", "name": "export_record", "description": "Export the record only after validation finds no issues.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"type": "function", "name": "human_review", "description": "Route an uncertain or invalid record to a human reviewer.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"], "additionalProperties": False}},
]

RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "address": {"type": "string"},
        "date_completed": {"type": "string"},
        "residents": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "date_of_birth": {"type": "string"}, "eligible_voter": {"type": "boolean"}}, "required": ["name", "date_of_birth", "eligible_voter"], "additionalProperties": False}},
    },
    "required": ["address", "date_completed", "residents"],
    "additionalProperties": False,
}

MEDIA_TOOLS = [
    {"type": "function", "name": "set_extracted_record", "description": "Save the fields you read from the uploaded document or image.", "parameters": {"type": "object", "properties": {"record": RECORD_SCHEMA}, "required": ["record"], "additionalProperties": False}},
    TOOLS[1], TOOLS[2], TOOLS[3],
]


class LLMToolLoopAgent:
    """Let the model choose tools while Python executes them safely."""

    def __init__(self, max_steps: int = 6):
        self.max_steps = max_steps
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-5.5")

    def _request(self, input_items: list[dict[str, Any]], tools: list[dict[str, Any]] = TOOLS, instructions: str | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Set OPENAI_API_KEY to use live LLM mode. The standard demo does not need one.")
        payload = json.dumps({
            "model": self.model,
            "instructions": instructions or (
                "You are a cautious Boston census data-entry agent. Work toward a clean, database-ready record. "
                "Use extract_fields first, then validate_record. Never export a record with validation issues. "
                "When information is missing, ambiguous, or invalid, use human_review."
            ),
            "input": input_items,
            "tools": tools,
            "store": False,
        }).encode()
        request = urllib.request.Request("https://api.openai.com/v1/responses", data=payload, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"OpenAI API error {error.code}: {detail}") from error

    def run(self, form_text: str) -> dict[str, Any]:
        record: dict[str, Any] = {}
        issues: list[dict[str, str]] = []
        audit = []
        input_items: list[dict[str, Any]] = [{"role": "user", "content": "Process this census form:\n" + form_text}]

        for step in range(1, self.max_steps + 1):
            response = self._request(input_items)
            output_items = response.get("output", [])
            input_items.extend(output_items)
            calls = [item for item in output_items if item.get("type") == "function_call"]
            if not calls:
                return {"status": "needs_review", "record": export_record(record), "issues": issues, "audit": audit + [{"step": step, "tool": "llm", "result": "No tool call; routed to review"}]}

            for call in calls:
                name = call.get("name")
                args = json.loads(call.get("arguments", "{}"))
                audit.append({"step": step, "tool": name, "result": args.get("reason", "Model selected tool")})
                if name == "extract_fields":
                    record = extract_fields(form_text)
                    tool_result = record
                elif name == "validate_record":
                    issues = validate_record(record)
                    tool_result = {"issues": issues}
                elif name == "export_record":
                    if not issues:
                        return {"status": "approved", "record": export_record(record), "issues": [], "audit": audit}
                    name = "human_review"
                    tool_result = {"status": "blocked", "reason": "Validation issues remain."}
                elif name == "human_review":
                    return {"status": "needs_review", "record": export_record(record), "issues": issues, "audit": audit}
                else:
                    tool_result = {"error": f"Unknown tool: {name}"}
                input_items.append({"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(tool_result)})

        return {"status": "needs_review", "record": export_record(record), "issues": issues, "audit": audit}

    def run_uploaded(self, filename: str, mime_type: str, data_url: str) -> dict[str, Any]:
        """Process a PDF or image by giving the uploaded file to the model."""
        if not self.api_key:
            raise RuntimeError("Set OPENAI_API_KEY to process PDFs or images with live mode.")
        if mime_type == "application/pdf":
            file_content = {"type": "input_file", "filename": filename, "file_data": data_url}
        elif mime_type.startswith("image/"):
            file_content = {"type": "input_image", "image_url": data_url, "detail": "high"}
        else:
            raise RuntimeError(f"Unsupported uploaded file type: {mime_type}")

        input_items: list[dict[str, Any]] = [{"role": "user", "content": [
            {"type": "input_text", "text": "Read this Boston census form. Extract every visible household and resident field. If the document is blurry or ambiguous, use human_review rather than guessing."},
            file_content,
        ]}]
        record: dict[str, Any] = {}
        issues: list[dict[str, str]] = []
        audit = []
        instructions = "You are a cautious document-intake agent. First call set_extracted_record with what you can read. Then validate_record. Never export a record with validation issues. Use human_review for ambiguity, illegibility, or missing data."

        for step in range(1, self.max_steps + 1):
            response = self._request(input_items, MEDIA_TOOLS, instructions)
            output_items = response.get("output", [])
            input_items.extend(output_items)
            calls = [item for item in output_items if item.get("type") == "function_call"]
            if not calls:
                return {"status": "needs_review", "record": export_record(record), "issues": issues + [{"field": "document", "severity": "review", "message": "The model did not produce a tool call."}], "audit": audit}
            for call in calls:
                name = call.get("name")
                args = json.loads(call.get("arguments", "{}"))
                audit.append({"step": step, "tool": name, "result": args.get("reason", "Model selected tool")})
                if name == "set_extracted_record":
                    record = args.get("record", {})
                    tool_result = record
                elif name == "validate_record":
                    issues = validate_record(record)
                    tool_result = {"issues": issues}
                elif name == "export_record":
                    if not issues:
                        return {"status": "approved", "record": export_record(record), "issues": [], "audit": audit}
                    tool_result = {"status": "blocked", "reason": "Validation issues remain."}
                elif name == "human_review":
                    return {"status": "needs_review", "record": export_record(record), "issues": issues, "audit": audit}
                else:
                    tool_result = {"error": f"Unknown tool: {name}"}
                input_items.append({"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(tool_result)})
        return {"status": "needs_review", "record": export_record(record), "issues": issues, "audit": audit}

