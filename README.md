# Boston Census Data Entry Agent

An educational prototype for reducing manual data entry in Boston's annual resident census process.

The app accepts a digital transcription of a census form, extracts structured fields, validates the result, and sends uncertain records to a human review queue. It uses fictional data only.

## Run locally

```bash
python app.py
```

Open http://localhost:8000 in a browser. The core prototype uses only Python's standard library.

## What makes this an agent?

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

