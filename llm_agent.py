"""Optional LLM-driven agent loop."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from tools import export_record, extract_fields, validate_record


class LLMToolLoopAgent:
    """Ask an LLM to choose the next tool, then execute that tool locally."""

    def __init__(self, max_steps: int = 5):
        self.max_steps = max_steps
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def ask_model(self, state: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Set OPENAI_API_KEY to use live LLM mode; demo mode does not need one.")
        payload = json.dumps({
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You are a cautious census data-entry agent. Return only valid JSON."},
                {"role": "user", "content": (
                    "Choose exactly one next action from extract, validate, export, or human_review. "
                    "Never approve a record with validation errors. Return JSON with action and reason. "
                    "Current state: " + json.dumps(state)
                )},
            ],
        }).encode()
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode())
        return json.loads(body["choices"][0]["message"]["content"])

    def run(self, form_text: str) -> dict[str, Any]:
        record: dict[str, Any] = {}
        issues: list[dict[str, str]] = []
        audit = []
        state: dict[str, Any] = {"record": record, "issues": issues}

        for step in range(1, self.max_steps + 1):
            decision = self.ask_model(state)
            action = decision.get("action")
            audit.append({"step": step, "tool": "llm_decision", "result": f"{action}: {decision.get('reason', '')}"})

            if action == "extract":
                record = extract_fields(form_text)
            elif action == "validate":
                issues = validate_record(record)
            elif action == "export":
                if not issues:
                    return {"status": "approved", "record": export_record(record), "issues": [], "audit": audit}
                action = "human_review"
            if action == "human_review":
                return {"status": "needs_review", "record": export_record(record), "issues": issues, "audit": audit}

            state = {"record": record, "issues": issues}
            audit.append({"step": step, "tool": action, "result": "Tool executed"})

        return {"status": "needs_review", "record": export_record(record), "issues": issues, "audit": audit}

