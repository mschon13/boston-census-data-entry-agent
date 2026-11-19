"""Zero-dependency local web app for the Boston Census Data Entry Agent."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from agent import CensusEntryAgent

FORMS = json.loads((Path(__file__).parent / "sample_data" / "forms.json").read_text())


def page(message: str = "") -> str:
    options = "".join(f'<option value="{html.escape(form["id"])}">{html.escape(form["id"])}</option>' for form in FORMS)
    default_text = html.escape(FORMS[0]["text"])
    form_map = json.dumps({f["id"]: f["text"] for f in FORMS}).replace("</", "<\\/")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Boston Census Data Entry Agent</title>
<style>body{{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#202938}}textarea{{width:100%;height:180px;font-family:monospace}}button{{background:#154734;color:white;border:0;padding:12px 18px;border-radius:5px;cursor:pointer}}select{{padding:8px}}.card{{border:1px solid #d5d9df;border-radius:8px;padding:18px;margin:18px 0}}.ok{{color:#176b3a}}.warn{{color:#9a5b00}}.bad{{color:#a32626}}pre{{white-space:pre-wrap;background:#f5f6f8;padding:14px;border-radius:5px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px;text-align:left}}</style>
<script>const forms={form_map};function loadForm(){{document.getElementById('formtext').value=forms[document.getElementById('formid').value];}}</script>
</head><body><h1>Boston Census Data Entry Agent</h1><p><em>Educational prototype using fictional census records only.</em></p>
<div class="card"><label for="formid">Choose a sample form:</label> <select id="formid" onchange="loadForm()">{options}</select>
<form method="post" action="/process"><textarea id="formtext" name="formtext">{default_text}</textarea><br><br><button>Run census entry agent</button></form></div>
{message}<div class="card"><h2>What this prototype demonstrates</h2><p>The agent extracts fields, validates them, records its tool calls, and safely routes uncertain or invalid records to human review.</p></div>
</body></html>"""


def render_result(result: dict) -> str:
    status = result["status"]
    css = "ok" if status == "approved" else "warn" if status == "ready_for_review" else "bad"
    issues = "<p>No issues found.</p>" if not result["issues"] else "<ul>" + "".join(
        f"<li><strong>{html.escape(i['severity'])}</strong> — {html.escape(i['message'])}</li>" for i in result["issues"]
    ) + "</ul>"
    audit = "<table><tr><th>Step</th><th>Tool</th><th>Result</th></tr>" + "".join(
        f"<tr><td>{a['step']}</td><td>{html.escape(a['tool'])}</td><td>{html.escape(a['result'])}</td></tr>" for a in result["audit"]
    ) + "</table>"
    record_json = html.escape(json.dumps(result["record"], indent=2))
    return f"<div class='card'><h2 class='{css}'>Status: {html.escape(status)}</h2><h3>Extracted record</h3><pre>{record_json}</pre><h3>Validation issues</h3>{issues}<h3>Agent audit trail</h3>{audit}</div>"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page().encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        form_text = parse_qs(body).get("formtext", [""])[0]
        result = CensusEntryAgent().run(form_text)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page(render_result(result)).encode())

    def log_message(self, *_args):
        return


if __name__ == "__main__":
    print("Boston Census Agent running at http://localhost:8000")
    HTTPServer(("localhost", 8000), Handler).serve_forever()

