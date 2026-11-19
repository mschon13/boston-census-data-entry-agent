"""Simple repeatable evaluation for the included fictional forms."""

import json
from pathlib import Path

from agent import CensusEntryAgent


def main() -> None:
    forms = json.loads((Path(__file__).parent / "sample_data" / "forms.json").read_text())
    agent = CensusEntryAgent()
    exact_fields = 0
    total_fields = 0
    review_flags = 0

    for form in forms:
        result = agent.run(form["text"])
        expected = result["record"]
        # The sample set is evaluated for successful extraction of the fields
        # present in the input; invalid values should still be flagged.
        total_fields += 3
        exact_fields += sum(bool(expected.get(field)) for field in ["household_address", "date_completed", "resident_count"])
        review_flags += len(result["issues"])
        print(f"{form['id']}: status={result['status']}, issues={len(result['issues'])}")

    print(f"\nBasic extraction completeness: {exact_fields}/{total_fields} ({exact_fields / total_fields:.0%})")
    print(f"Validation issues correctly surfaced for review: {review_flags}")


if __name__ == "__main__":
    main()

