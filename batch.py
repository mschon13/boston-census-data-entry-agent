"""Batch ingestion and master-record export helpers."""

from __future__ import annotations

import base64
import csv
import io
import json
from typing import Any

from agent import CensusEntryAgent
from llm_agent import LLMToolLoopAgent


def decode_data_url(data_url: str) -> bytes:
    return base64.b64decode(data_url.split(",", 1)[-1])


def normalize_csv(raw: bytes) -> str:
    """Turn the simple sample CSV format into the agent's canonical text form."""
    rows = csv.DictReader(io.StringIO(raw.decode(errors="replace")))
    fields = {row.get("field", "").strip(): row.get("value", "").strip() for row in rows}
    lines = ["Boston Resident Census 2026"]
    if fields.get("household_address"):
        lines.append(f"Household address: {fields['household_address']}")
    index = 1
    while fields.get(f"resident_{index}"):
        parts = [part.strip() for part in fields[f"resident_{index}"].split("|")]
        if len(parts) >= 3:
            lines.append(f"Resident {index}: {parts[0]} | Date of birth: {parts[1]} | Eligible voter: {parts[2]}")
        index += 1
    if fields.get("date_completed"):
        lines.append(f"Date completed: {fields['date_completed']}")
    return "\n".join(lines)


def process_file(file_item: dict[str, Any], live_llm: bool) -> dict[str, Any]:
    filename = file_item.get("filename", "upload")
    mime_type = file_item.get("mime_type", "")
    data_url = file_item.get("data_url", "")
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    raw = decode_data_url(data_url) if data_url else b""

    if suffix in {"pdf", "png", "jpg", "jpeg"} or mime_type == "application/pdf" or mime_type.startswith("image/"):
        if not live_llm:
            return {"status": "needs_review", "record": {}, "issues": [{"field": "file", "severity": "error", "message": "PDF and image files require live OpenAI mode."}], "audit": []}
        return LLMToolLoopAgent().run_uploaded(filename, mime_type, data_url)

    text = normalize_csv(raw) if suffix == "csv" else raw.decode(errors="replace")
    return LLMToolLoopAgent().run(text) if live_llm else CensusEntryAgent().run(text)


def master_csv(results: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    columns = ["source_file", "status", "household_address", "date_completed", "resident_count", "residents", "review_issues"]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for item in results:
        record = item["result"].get("record", {})
        writer.writerow({
            "source_file": item["filename"],
            "status": item["result"].get("status", ""),
            "household_address": record.get("household_address", record.get("address", "")),
            "date_completed": record.get("date_completed", ""),
            "resident_count": record.get("resident_count", len(record.get("residents", []))),
            "residents": json.dumps(record.get("residents", [])),
            "review_issues": json.dumps(item["result"].get("issues", [])),
        })
    return output.getvalue()


def add_cross_file_checks(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag repeated household addresses across separate uploaded files."""
    seen: dict[str, int] = {}
    for index, item in enumerate(results):
        record = item["result"].get("record", {})
        address = (record.get("household_address") or record.get("address") or "").strip().lower()
        if not address:
            continue
        if address in seen:
            previous = results[seen[address]]
            issue = {"field": "household_address", "severity": "review", "message": "Possible duplicate household address across uploaded files."}
            previous["result"].setdefault("issues", []).append(issue)
            item["result"].setdefault("issues", []).append(issue)
            previous["result"]["status"] = "needs_review"
            item["result"]["status"] = "needs_review"
        else:
            seen[address] = index
    return results

