"""Zero-dependency local web app for the Boston Census Data Entry Agent."""

from __future__ import annotations

import html
import json
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from agent import CensusEntryAgent
from llm_agent import LLMToolLoopAgent

FORMS = json.loads((Path(__file__).parent / "sample_data" / "forms.json").read_text())


def page(message: str = "") -> str:
    options = "".join(f'<option value="{html.escape(form["id"])}">{html.escape(form["id"])}</option>' for form in FORMS)
    default_text = html.escape(FORMS[0]["text"])
    form_map = json.dumps({f["id"]: f["text"] for f in FORMS}).replace("</", "<\\/")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Boston Census Data Entry Agent</title>
<style>body{{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#202938}}textarea{{width:100%;height:180px;font-family:monospace}}button{{background:#154734;color:white;border:0;padding:12px 18px;border-radius:5px;cursor:pointer}}select{{padding:8px}}.card{{border:1px solid #d5d9df;border-radius:8px;padding:18px;margin:18px 0}}.ok{{color:#176b3a}}.warn{{color:#9a5b00}}.bad{{color:#a32626}}pre{{white-space:pre-wrap;background:#f5f6f8;padding:14px;border-radius:5px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px;text-align:left}}</style>
<script>const forms={form_map};function loadForm(){{document.getElementById('formtext').value=forms[document.getElementById('formid').value];}}function readFile(){{const f=document.getElementById('upload').files[0];if(f&&!f.type.startsWith('image/')&&f.type!=='application/pdf'){{const r=new FileReader();r.onload=()=>document.getElementById('formtext').value=r.result;r.readAsText(f);}}else if(f){{document.getElementById('formtext').value='Binary file selected: '+f.name+'. Check live OpenAI mode to process it.';}}}}async function submitEntry(event){{const f=document.getElementById('upload').files[0];if(!f||(!f.type.startsWith('image/')&&f.type!=='application/pdf'))return;event.preventDefault();const live=document.querySelector('input[name=live_llm]').checked;if(!live){{alert('PDF and image files require live OpenAI mode.');return;}}const reader=new FileReader();reader.onload=async()=>{{const response=await fetch('/process',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{filename:f.name,mime_type:f.type,data_url:reader.result,live_llm:true}})}});document.open();document.write(await response.text());document.close();}};reader.readAsDataURL(f);}}</script>
</head><body><h1>Boston Census Data Entry Agent</h1><p><em>Educational prototype using fictional census records only.</em></p>
<div class="card"><label for="formid">Choose a sample form:</label> <select id="formid" onchange="loadForm()">{options}</select>
<p>Upload <strong>.txt</strong>, <strong>.csv</strong>, <strong>.json</strong>, <strong>.pdf</strong>, <strong>.png</strong>, or <strong>.jpg</strong> files:</p><input type="file" id="upload" accept=".txt,.csv,.json,.pdf,.png,.jpg,.jpeg" onchange="readFile()">
<form id="entryform" method="post" action="/process" onsubmit="submitEntry(event)"><textarea id="formtext" name="formtext">{default_text}</textarea><br><label><input type="checkbox" name="live_llm" value="yes"> Use live OpenAI agent (required for PDF/image files)</label><br><br><button>Run census entry agent</button></form></div>
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
        raw_body = self.rfile.read(length)
        if self.headers.get("Content-Type", "").startswith("application/json"):
            payload = json.loads(raw_body.decode())
            mime_type = payload.get("mime_type", "")
            live_llm = payload.get("live_llm", False)
            if mime_type in {"application/pdf"} or mime_type.startswith("image/"):
                try:
                    result = LLMToolLoopAgent().run_uploaded(payload.get("filename", "upload"), mime_type, payload.get("data_url", "")) if live_llm else {"status": "needs_review", "record": {}, "issues": [{"field": "file", "severity": "error", "message": "PDF and image files require live OpenAI mode."}], "audit": []}
                except Exception as error:
                    result = {"status": "needs_review", "record": {}, "issues": [{"field": "agent", "severity": "error", "message": str(error)}], "audit": [{"step": 1, "tool": "live_llm", "result": "The live agent could not run"}]}
            else:
                encoded = payload.get("data_url", "")
                form_text = base64.b64decode(encoded.split(",", 1)[-1]).decode(errors="replace") if encoded else payload.get("text", "")
                result = LLMToolLoopAgent().run(form_text) if live_llm else CensusEntryAgent().run(form_text)
        else:
            body = raw_body.decode()
            parsed = parse_qs(body)
            form_text = parsed.get("formtext", [""])[0]
            if "live_llm" in parsed:
                try:
                    result = LLMToolLoopAgent().run(form_text)
                except Exception as error:
                    result = {"status": "needs_review", "record": {}, "issues": [{"field": "agent", "severity": "error", "message": str(error)}], "audit": [{"step": 1, "tool": "live_llm", "result": "The live agent could not run"}]}
            else:
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

