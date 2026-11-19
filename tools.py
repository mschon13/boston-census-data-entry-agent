"""Tools the census agent can call during its processing loop."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def extract_fields(form_text: str) -> dict[str, Any]:
    """Extract likely fields from a simple digital transcription."""
    address_match = re.search(r"Household address:\s*(.+)", form_text, re.I)
    completed_match = re.search(r"Date completed:\s*([^\n]+)", form_text, re.I)

    residents = []
    pattern = re.compile(
        r"Resident\s+\d+:\s*(.*?)\s*\|\s*Date of birth:\s*([^|]+)\s*\|\s*Eligible voter:\s*(yes|no)",
        re.I,
    )
    for match in pattern.finditer(form_text):
        residents.append(
            {
                "name": match.group(1).strip(),
                "date_of_birth": match.group(2).strip(),
                "eligible_voter": match.group(3).strip().lower() == "yes",
            }
        )

    return {
        "address": address_match.group(1).strip() if address_match else "",
        "residents": residents,
        "date_completed": completed_match.group(1).strip() if completed_match else "",
    }


def validate_record(record: dict[str, Any]) -> list[dict[str, str]]:
    """Return structured validation issues for human review."""
    issues: list[dict[str, str]] = []
    if not record.get("address"):
        issues.append({"field": "address", "severity": "error", "message": "Household address is missing."})
    if not record.get("residents"):
        issues.append({"field": "residents", "severity": "error", "message": "No residents were extracted."})
    if not record.get("date_completed"):
        issues.append({"field": "date_completed", "severity": "warning", "message": "Completion date is missing."})

    for index, resident in enumerate(record.get("residents", []), start=1):
        if not resident.get("name"):
            issues.append({"field": f"resident_{index}.name", "severity": "error", "message": "Resident name is missing."})
        dob = resident.get("date_of_birth", "")
        if not dob or dob.upper() in {"UNKNOWN", "N/A", "NA"}:
            issues.append({"field": f"resident_{index}.date_of_birth", "severity": "review", "message": "Date of birth requires review."})
        else:
            try:
                datetime.strptime(dob, "%m/%d/%Y")
            except ValueError:
                issues.append({"field": f"resident_{index}.date_of_birth", "severity": "error", "message": f"Invalid date: {dob}."})

    names = [r.get("name", "").lower() for r in record.get("residents", [])]
    if len(names) != len(set(names)):
        issues.append({"field": "residents", "severity": "review", "message": "Possible duplicate resident detected."})
    return issues


def export_record(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten a validated record into a database-ready shape."""
    return {
        "household_address": record.get("address", ""),
        "date_completed": record.get("date_completed", ""),
        "resident_count": len(record.get("residents", [])),
        "residents": record.get("residents", []),
    }

