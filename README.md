# Boston Census Data Entry Agent

An educational prototype for reducing manual data entry in Boston's annual resident census process.

## Problem

Election staff may need to transcribe information from paper or digitally collected census forms into a state database. This is repetitive, slow, and vulnerable to transcription errors. The prototype explores whether an AI-assisted workflow can automate routine extraction while preserving human review for uncertain records.

## What the prototype does

The app accepts a digital transcription of a census form, extracts structured fields, validates the result, and sends uncertain records to a human review queue. It uses fictional data only.

- Clean records can be approved for export.
- Missing or uncertain information is flagged for review.
- Invalid dates and other blocking errors are not silently accepted.
- An audit trail records which tools the agent used and why.
- Approved records can be exported in a database-ready structure.

## Run locally

```bash
python app.py
```

Open http://localhost:8000 in a browser. The core prototype uses only Python's standard library.

## Agent design

The project follows Simon Willison's definition: “An LLM agent runs tools in a loop to achieve a goal.”

**Goal:** Convert a census form into an accurate, structured record while minimizing manual data entry.

**Tools:** Field extraction, validation, duplicate checking, human-review routing, and record export.

**Loop:** Extract → validate → decide whether to approve or route to review → export only safe records.

**Human control:** The system is designed to abstain when information is missing, ambiguous, or invalid. It does not write to a production government database.

The standard demo uses a transparent local extraction tool so it runs without an API key. `llm_agent.py` contains an optional live LLM-driven version in which the model chooses the next tool and Python executes it.

## What makes the demo an agent?

The agent works toward a goal by repeatedly using tools:

1. Extract fields from the submitted form.
2. Validate the extracted record.
3. Decide whether it needs another extraction pass or human review.
4. Export only records that pass validation or have been approved by a reviewer.

This prototype intentionally does not connect to Boston's or Massachusetts's production systems and does not process real resident information.

## Optional live LLM mode

The standard demo is fully local and needs no API key. The optional LLM-driven tool loop can be enabled with an API key:

```bash
export OPENAI_API_KEY="your-key-here"
```

The model chooses the next action, while Python executes the extraction, validation, export, and human-review tools. Never use real resident data or place an API key in GitHub.

## Evaluation

Run the included evaluation script:

```bash
python evaluation.py
```

It compares the agent's output with fictional ground-truth records and reports field-level accuracy, validation performance, and review flags.

The included three-form test set produced these results:

| Form | Input condition | Result |
|---|---|---|
| FORM-001 | Complete, valid record | Approved |
| FORM-002 | Unknown date of birth | Sent to human review |
| FORM-003 | Invalid date (`02/30/1985`) | Blocked and sent to review |

The basic extraction completeness score was 100% for the fields present in the test set. This is a small demonstration, not evidence that the system is ready for production use.

## Limitations and next steps

- The current demo accepts digital transcriptions rather than directly reading handwriting or scanned images.
- The sample size is intentionally small and uses fictional data.
- A production system would require OCR, security review, privacy protections, accessibility testing, integration with approved databases, and much larger validation datasets.
- The agent should remain human-in-the-loop for ambiguous records.

