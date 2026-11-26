"""Build Technical Report PDF and 7-Section Milestone 2 PDF via Chrome Headless."""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHROME_EXE = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def load_json_safe(path: Path) -> Any:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def parse_prompt_md(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    sys_m = re.search(r"## System Prompt\s*\n(.*?)\n## User Prompt Template\s*\n(.*)\Z", text, flags=re.DOTALL)
    sys_p = sys_m.group(1).strip() if sys_m else ""
    usr_p = sys_m.group(2).strip() if sys_m else text.strip()
    meta: dict[str, str] = {"system": sys_p, "user": usr_p, "raw": text}
    for line in text.splitlines():
        m = re.match(r"^- \*\*(.+?):\*\*\s*(.+)$", line.strip())
        if m:
            meta[m.group(1).strip()] = m.group(2).strip()
    return meta


def img_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    mime = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def summarize_eval(records: list[dict[str, Any]]) -> dict[str, str]:
    n = len(records)
    if n == 0:
        return {"n": "0", "json": "0/0", "marks": "0/0", "bloom": "0/0"}
    j = sum(1 for r in records if r.get("valid_json"))
    m = sum(1 for r in records if r.get("marks_match"))
    b = sum(1 for r in records if r.get("bloom_ok"))
    return {"n": str(n), "json": f"{j}/{n}", "marks": f"{m}/{n}", "bloom": f"{b}/{n}"}


def common_css() -> str:
    return """
    @page { size: A4; margin: 15mm 14mm 16mm 14mm; }
    * { box-sizing: border-box; }
    body {
      font-family: "Segoe UI", Arial, sans-serif;
      color: #1e293b;
      font-size: 10pt;
      line-height: 1.45;
      margin: 0;
    }
    h1 { font-size: 18pt; color: #0f172a; margin: 0 0 6px 0; border-bottom: 2.5px solid #1d4ed8; padding-bottom: 6px; }
    h2 { font-size: 13.5pt; color: #1e3a8a; margin: 16px 0 6px 0; border-bottom: 1px solid #cbd5e1; padding-bottom: 3px; page-break-after: avoid; }
    h3 { font-size: 11pt; color: #0f172a; margin: 11px 0 4px 0; page-break-after: avoid; }
    p { margin: 5px 0 8px 0; }
    ul { margin: 4px 0 8px 18px; padding: 0; }
    li { margin-bottom: 3px; }
    table { width: 100%; border-collapse: collapse; margin: 8px 0 12px 0; font-size: 8.8pt; }
    th, td { border: 1px solid #cbd5e1; padding: 5px 7px; text-align: left; vertical-align: top; word-wrap: break-word; }
    th { background-color: #1e3a8a; color: #ffffff; font-weight: 600; }
    tr:nth-child(even) td { background-color: #f8fafc; }
    pre, code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 8pt;
      background: #f1f5f9;
      border-radius: 4px;
    }
    pre {
      padding: 8px 10px;
      border: 1px solid #cbd5e1;
      white-space: pre-wrap;
      word-break: break-word;
      margin: 5px 0 10px 0;
    }
    code { padding: 1px 4px; }
    .page-break { page-break-before: always; }
    .avoid-break { page-break-inside: avoid; }
    .box { background: #eff6ff; border-left: 4px solid #2563eb; padding: 8px 12px; margin: 8px 0; border-radius: 4px; }
    .warn-box { background: #fefce8; border-left: 4px solid #ca8a04; padding: 8px 12px; margin: 8px 0; border-radius: 4px; }
    .diagram-card { border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px; margin: 8px 0 12px 0; text-align: center; page-break-inside: avoid; background: #fff; }
    .diagram-card img { max-width: 100%; height: auto; max-height: 245px; }
    .screenshot-card { border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px; margin: 8px 0 12px 0; text-align: center; page-break-inside: avoid; }
    .screenshot-card img { max-width: 100%; max-height: 300px; border: 1px solid #e2e8f0; }
    .caption { font-size: 8.5pt; color: #475569; margin-top: 5px; font-style: italic; }
    .badge-pass { color: #166534; font-weight: bold; }
    .badge-fail { color: #991b1b; font-weight: bold; }
    .cover-header { background: linear-gradient(135deg, #1e3a8a, #2563eb); color: #ffffff; padding: 18px 20px; border-radius: 8px; margin-bottom: 14px; }
    .cover-header h1 { color: #ffffff; border: none; margin: 0 0 6px 0; padding: 0; font-size: 19pt; }
    """


def build_technical_report_body(
    v1_eval: list[dict[str, Any]],
    v2_eval: list[dict[str, Any]],
    v3_eval: list[dict[str, Any]],
    test_results: list[dict[str, Any]],
) -> str:
    s1 = summarize_eval(v1_eval)
    s2 = summarize_eval(v2_eval)
    s3 = summarize_eval(v3_eval)
    n12 = len(test_results)
    p12 = sum(1 for r in test_results if r.get("pass_fail") == "Pass")
    normal_pass = sum(1 for r in test_results if r.get("type") == "Normal" and r.get("pass_fail") == "Pass")
    normal_tot = sum(1 for r in test_results if r.get("type") == "Normal")
    edge_pass = sum(1 for r in test_results if r.get("type") == "Edge" and r.get("pass_fail") == "Pass")
    edge_tot = sum(1 for r in test_results if r.get("type") == "Edge")
    inv_pass = sum(1 for r in test_results if r.get("type") == "Invalid" and r.get("pass_fail") == "Pass")
    inv_tot = sum(1 for r in test_results if r.get("type") == "Invalid")

    arch_uri = img_data_uri(ROOT / "docs" / "diagrams" / "04_system_architecture.svg")

    return f"""
    <h1>Technical Report — AssessMate: Exam Question Generator with Quality Check</h1>
    <p><strong>Team ID:</strong> PE-B65-48 | <strong>Team Name:</strong> BEYOND THE PROMPT | <strong>Problem Pool ID:</strong> C3 | <strong>Course:</strong> SCSE4041 (Bennett University)</p>
    <p><strong>Members:</strong> Jayant Kriplani (S24CSEU2763), Shubham Mittal (S24CSEU2764), Ajay Chopra (S24CSEU2827) | <strong>Faculty:</strong> Sonal Kukreja</p>

    <h2>1. System Architecture &amp; Grounding Design</h2>
    <p>AssessMate solves Problem C3 by replacing single-shot exam generation with a <strong>4-module retrieval-grounded chained architecture</strong>. Module 1 (<code>code/rag.py</code>) validates user constraints and performs lightweight TF-IDF chunk retrieval over either an uploaded PDF/text syllabus or a 7-topic public Computer Science syllabus corpus. Retrieved passages are injected into a 3-prompt sequential pipeline (<code>code/pipeline.py</code>) exposed via a Streamlit web interface (<code>code/app.py</code>):</p>
    <ul>
      <li><strong>Prompt P1 (Question Generator, T=0.2):</strong> Synthesizes exam questions strictly from retrieved syllabus excerpts using Revised Bloom's cognitive action verbs, question-type formatting rules (MCQ, Short Answer, Long Answer, Numerical), and out-of-syllabus refusal guardrails.</li>
      <li><strong>Prompt P2 (Answer Key &amp; Marking Scheme, T=0.2):</strong> Produces syllabus-grounded model answers and observable stepwise marking criteria verified deterministically in Python so rubric sums match target marks.</li>
      <li><strong>Prompt P3 (Independent Quality Reviewer, T=0.1):</strong> Audits every question-solution pair on a 1–5 scale across five rubric axes (Clarity, Syllabus Relevance, Answerability, Bloom's Alignment, Difficulty), triggers <code>REVISE</code> with a concrete rewrite when any axis scores below 4, and enforces human faculty sign-off.</li>
    </ul>
    <div class="diagram-card">
      <img src="{arch_uri}" alt="System Architecture"/>
      <div class="caption">Figure 1: Four-module AssessMate system architecture connecting Streamlit, TF-IDF RAG, and Gemini Flash-Lite fallback APIs.</div>
    </div>

    <h2>2. Tools, Models &amp; API Resilience</h2>
    <p>Built in Python 3.13 with Streamlit, <code>pypdf</code>, and the official <code>google-genai</code> SDK. During live API validation, <code>gemini-2.5-flash</code> returned HTTP 404 (deprecated for new keys) and <code>gemini-3-flash-preview</code> hit a 20 requests/day free-tier ceiling. To ensure uninterrupted availability for evaluators, the orchestration layer routes JSON-mode requests through <code>gemini-flash-lite-latest</code> with automatic fallback to <code>gemini-3.5-flash-lite</code> and exponential backoff against peak-hour HTTP 503 load spikes. API keys are resolved exclusively from environment variables or Streamlit Cloud Secrets and are excluded from Git via <code>.gitignore</code>.</p>

    <h2>3. Prompt Design &amp; Iterative Engineering Results</h2>
    <p>Prompts evolved across four saved versions benchmarked on six CS syllabus test cases (<code>B1</code>–<code>B6</code>):</p>
    <table>
      <tr><th>Version</th><th>Key Engineering Change</th><th>JSON Validity</th><th>Mark-Sum Match</th><th>Bloom Verb Match</th></tr>
      <tr><td><strong>v1 (M1 Baseline)</strong></td><td>Monolithic zero-shot generator + prose reviewer</td><td>{s1['json']}</td><td>Manual prose</td><td>Drifted on B4</td></tr>
      <tr><td><strong>v2 (Decomposed)</strong></td><td>Split into P1/P2/P3 + JSON schemas + P1 refusal</td><td>{s2['json']}</td><td>{s2['marks']}</td><td>{s2['bloom']}</td></tr>
      <tr><td><strong>v3 (Few-Shot + Rubric)</strong></td><td>Added Bloom verb list, MCQ rules, few-shot JSON, 5-axis rubric</td><td>{s3['json']}</td><td>{s3['marks']}</td><td>{s3['bloom']}</td></tr>
      <tr><td><strong>v4 (Final Production)</strong></td><td>Formal English lock, temperature tuning (0.2/0.1), full {n12}-case test suite</td><td colspan="3"><strong>{p12}/{n12} Tests Passed</strong> (Normal {normal_pass}/{normal_tot}, Edge {edge_pass}/{edge_tot}, Invalid {inv_pass}/{inv_tot})</td></tr>
    </table>

    <h2>4. Evaluation &amp; Key Limitations</h2>
    <p>Across the {n12}-case evaluation suite (<code>test-data/test_results.json</code>), AssessMate passed <strong>{p12} out of {n12}</strong> tests (including 1 honest Edge failure on Test 13 where lexical TF-IDF missed a paraphrased synonym query), demonstrating exact rubric arithmetic, MCQ option formatting, Hinglish-to-academic English normalization, out-of-syllabus rejection, and <code>REVISE</code> flagging on over-scoped 2-mark requests. Known limitations to address in Milestone 3 include: (1) TF-IDF lexical chunk matching can miss semantic synonyms compared to dense embeddings (observed in Test 13); (2) single-pass P3 scoring can vary slightly across stochastic runs (solvable with multi-pass self-consistency); (3) peak-hour free-tier HTTP 503 spikes add latency; and (4) STEM diagrams/LaTeX equations currently output as plain text/Markdown rather than rendered figures.</p>
    """


def build_prompt_sheet_html(pid: str, title: str, step: str, md_path: Path, vars_desc: str, sample_in: str, sample_out: str) -> str:
    data = parse_prompt_md(md_path)
    return f"""
    <div class="avoid-break" style="border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 12px; margin-bottom: 12px;">
      <h3 style="margin-top:0; color:#1e3a8a;">Prompt Sheet — {esc(pid)}: {esc(title)}</h3>
      <table>
        <tr><th style="width:24%;">Field</th><th>Details</th></tr>
        <tr><td><strong>Prompt ID &amp; Name</strong></td><td>{esc(pid)} — {esc(title)}</td></tr>
        <tr><td><strong>Step in Workflow</strong></td><td>{esc(step)}</td></tr>
        <tr><td><strong>Purpose</strong></td><td>{esc(data.get('Purpose', ''))}</td></tr>
        <tr><td><strong>Tool and Model</strong></td><td>{esc(data.get('Tool and Model', 'Gemini Flash-Lite via google-genai SDK'))}</td></tr>
        <tr><td><strong>Settings</strong></td><td>{esc(data.get('Settings', 'default'))}</td></tr>
        <tr><td><strong>Examples Included</strong></td><td>{esc(data.get('Number of Examples Included', '0'))}</td></tr>
        <tr><td><strong>Output Format</strong></td><td>Strict JSON matching schema at end of template</td></tr>
        <tr><td><strong>Template Variables</strong></td><td>{esc(vars_desc)}</td></tr>
      </table>
      <p><strong>Full System Prompt:</strong></p>
      <pre>{esc(data['system'])}</pre>
      <p><strong>Full User Prompt Template:</strong></p>
      <pre>{esc(data['user'])}</pre>
      <p><strong>Sample Run (Real Input &amp; Actual Output):</strong></p>
      <pre>INPUT: {esc(sample_in)}\n\nACTUAL OUTPUT:\n{esc(sample_out)}</pre>
    </div>
    """


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proto-url", default="https://assessmate-pe-b65-48-ievwpkiytzlhkjngeyagn9.streamlit.app/")
    parser.add_argument("--repo-url", default="https://github.com/jayantkriplani0-crypto/AssessMate-PE-B65-48")
    parser.add_argument("--reel-url", default="https://drive.google.com/file/d/12TF8VMWENLZ4jR9CT6AiHK__72HW8tvJ/view?usp=sharing")
    parser.add_argument("--reel-len", default="141")
    args = parser.parse_args()

    v1_eval = load_json_safe(ROOT / "test-data" / "v1_baseline_eval.json")
    v2_eval = load_json_safe(ROOT / "test-data" / "v2_eval.json")
    v3_eval = load_json_safe(ROOT / "test-data" / "v3_eval.json")
    test_results = load_json_safe(ROOT / "test-data" / "test_results.json")

    s1, s2, s3 = summarize_eval(v1_eval), summarize_eval(v2_eval), summarize_eval(v3_eval)
    p12 = sum(1 for r in test_results if r.get("pass_fail") == "Pass")
    n12 = len(test_results)

    # 1. Build Technical Report PDF
    tech_body = build_technical_report_body(v1_eval, v2_eval, v3_eval, test_results)
    tech_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{common_css()}</style></head><body>{tech_body}</body></html>"
    tech_html_path = ROOT / "docs" / "_technical_report.html"
    tech_html_path.write_text(tech_html, encoding="utf-8")

    # 2. Extract real sample run from Test 1 for Prompt Sheets
    t1_rec = next((r for r in test_results if r.get("test_no") == 1), None)
    if t1_rec and t1_rec.get("full_response"):
        fr = t1_rec["full_response"]
        p1_sample_in = "Topic: Binary Search Trees: deletion and inorder traversal | Bloom: Apply | Type: Short Answer | 2 x 5 Marks"
        p1_sample_out = json.dumps(fr.get("p1_output", {}), indent=2)[:1100]
        p2_sample_in = "Questions JSON from P1 (Q1, Q2) | Marks per Question: 5"
        p2_sample_out = json.dumps(fr.get("p2_output", {}), indent=2)[:1100]
        p3_sample_in = "Package JSON (Questions + Solutions from P1 & P2) | Bloom: Apply | Marks: 5"
        p3_sample_out = json.dumps(fr.get("p3_output", {}), indent=2)[:1100]
    else:
        p1_sample_in = p1_sample_out = p2_sample_in = p2_sample_out = p3_sample_in = p3_sample_out = "Pending test run"

    # Prompt Sheets
    ps1 = build_prompt_sheet_html(
        "P1",
        "Exam Question Generator",
        "Step 1 of 3 (after Module 1 RAG & Input Validator)",
        ROOT / "prompts" / "final" / "P1_question_generator.md",
        "{syllabus_excerpt}: retrieved top-2 passages; {topic}: syllabus topic; {learning_outcome}: course outcome; {bloom_level}: Revised Bloom level; {difficulty}: Easy/Medium/Hard; {question_type}: MCQ/Short/Long/Numerical; {num_questions}: count; {marks_per_question}: marks; {constraints}: exam constraints",
        p1_sample_in,
        p1_sample_out,
    )
    ps2 = build_prompt_sheet_html(
        "P2",
        "Answer Key & Marking Scheme Generator",
        "Step 2 of 3",
        ROOT / "prompts" / "final" / "P2_answer_key_rubric.md",
        "{syllabus_excerpt}: retrieved passages; {bloom_level}: target level; {marks_per_question}: target total marks; {questions_json}: JSON list generated by P1",
        p2_sample_in,
        p2_sample_out,
    )
    ps3 = build_prompt_sheet_html(
        "P3",
        "Quality Check Reviewer & Revision Engine",
        "Step 3 of 3 (Independent moderation critic)",
        ROOT / "prompts" / "final" / "P3_quality_reviewer.md",
        "{syllabus_excerpt}: retrieved passages; {topic}: target topic; {bloom_level}: target level; {difficulty}: target difficulty; {marks_per_question}: target marks; {package_json}: combined P1 questions and P2 solutions JSON",
        p3_sample_in,
        p3_sample_out,
    )

    # Full prompt versions text for Section 3
    v1_p1 = parse_prompt_md(ROOT / "prompts" / "v1" / "P1_baseline_generation.md")
    v1_p2 = parse_prompt_md(ROOT / "prompts" / "v1" / "P2_baseline_reviewer.md")
    v2_p1 = parse_prompt_md(ROOT / "prompts" / "v2" / "P1_question_generator.md")
    v2_p2 = parse_prompt_md(ROOT / "prompts" / "v2" / "P2_answer_key_rubric.md")
    v2_p3 = parse_prompt_md(ROOT / "prompts" / "v2" / "P3_quality_reviewer.md")
    v3_p1 = parse_prompt_md(ROOT / "prompts" / "v3" / "P1_question_generator.md")
    v3_p2 = parse_prompt_md(ROOT / "prompts" / "v3" / "P2_answer_key_rubric.md")
    v3_p3 = parse_prompt_md(ROOT / "prompts" / "v3" / "P3_quality_reviewer.md")
    v4_p1 = parse_prompt_md(ROOT / "prompts" / "final" / "P1_question_generator.md")
    v4_p2 = parse_prompt_md(ROOT / "prompts" / "final" / "P2_answer_key_rubric.md")
    v4_p3 = parse_prompt_md(ROOT / "prompts" / "final" / "P3_quality_reviewer.md")

    # Test rows HTML
    test_rows = []
    for r in test_results:
        badge_cls = "badge-pass" if r.get("pass_fail") == "Pass" else "badge-fail"
        test_rows.append(
            f"<tr><td>{r['test_no']}</td><td>{esc(r['input_short'])}</td><td>{esc(r['type'])}</td>"
            f"<td>{esc(r['expected_output'])}</td><td>{esc(r['actual_output_short'])}</td>"
            f"<td class='{badge_cls}'>{esc(r['pass_fail'])}</td></tr>"
        )
    test_rows_html = "\n".join(test_rows)

    # Diagrams
    d1 = img_data_uri(ROOT / "docs" / "diagrams" / "01_prompt_workflow.svg")
    d2 = img_data_uri(ROOT / "docs" / "diagrams" / "02_task_decomposition.svg")
    d3 = img_data_uri(ROOT / "docs" / "diagrams" / "03_io_flow.svg")
    d4 = img_data_uri(ROOT / "docs" / "diagrams" / "04_system_architecture.svg")
    d5 = img_data_uri(ROOT / "docs" / "diagrams" / "05_rag_pipeline.svg")

    # Screenshots (if captured)
    sc_test1 = img_data_uri(ROOT / "docs" / "screenshots" / "test1_normal.png")
    sc_test10 = img_data_uri(ROOT / "docs" / "screenshots" / "test10_edge_revise.png")
    sc_test11 = img_data_uri(ROOT / "docs" / "screenshots" / "test11_invalid_reject.png")
    sc_repo = img_data_uri(ROOT / "docs" / "screenshots" / "repo_structure.png")

    def sc_block(uri: str, cap: str) -> str:
        if not uri:
            return f"<div class='warn-box'>Screenshot pending: {esc(cap)}</div>"
        return f"<div class='screenshot-card'><img src='{uri}' alt='{esc(cap)}'/><div class='caption'>{esc(cap)}</div></div>"

    m2_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{common_css()}</style></head>
<body>

  <!-- SECTION 1 -->
  <h1>1. Cover page</h1>
  <div class="cover-header">
    <h1>AssessMate: Exam Question Generator with Quality Check</h1>
    <div>SCSE4041 Prompt Engineering — Milestone 2 Submission (Problem Pool ID: C3)</div>
  </div>
  <table>
    <tr><th style="width:28%;">Field</th><th>Project Details</th></tr>
    <tr><td><strong>Team ID</strong></td><td>PE-B65-48</td></tr>
    <tr><td><strong>Team Name</strong></td><td>BEYOND THE PROMPT</td></tr>
    <tr><td><strong>Project Title</strong></td><td>AssessMate: Exam Question Generator with Quality Check</td></tr>
    <tr><td><strong>Batch / Group</strong></td><td>B75 (Group B65-80)</td></tr>
    <tr><td><strong>Faculty Name</strong></td><td>Sonal Kukreja</td></tr>
    <tr><td><strong>Team Members</strong></td><td>
      Jayant Kriplani — <code>S24CSEU2763</code> (Team Leader)<br/>
      Shubham Mittal — <code>S24CSEU2764</code><br/>
      Ajay Chopra — <code>S24CSEU2827</code>
    </td></tr>
    <tr><td><strong>Prototype Link (Q11)</strong></td><td><code>{esc(args.proto_url)}</code></td></tr>
    <tr><td><strong>GitHub Repository Link (Q12)</strong></td><td><code>{esc(args.repo_url)}</code></td></tr>
    <tr><td><strong>Reel Link &amp; Length (Q13–Q14)</strong></td><td><code>{esc(args.reel_url)}</code> ({esc(args.reel_len)} seconds)</td></tr>
    <tr><td><strong>Submission Counts</strong></td><td>Final Prompts: <strong>3</strong> | Test Inputs: <strong>{n12}</strong> | Prompt Versions: <strong>4</strong></td></tr>
  </table>

  <div class="page-break"></div>

  <!-- SECTION 2 -->
  <h1>2. Prompt and solution design</h1>
  <h2>2(a) Solution Overview &amp; Design Rationale</h2>
  <p><strong>What problem and for whom:</strong> University faculty, teaching assistants, and examination coordinators spend substantial time drafting syllabus-aligned exam questions at specific Revised Bloom's taxonomy levels along with consistent model answers and marking schemes. As noted in a 2024 Indian curriculum study (510 AI-generated questions evaluated by expert reviewers, 91.56% rated high quality), generative AI aids authoring but still requires systematic moderation for clarity, cognitive alignment, and factual accuracy. <strong>AssessMate</strong> automates both generation and pre-submission moderation while preserving final faculty sign-off.</p>
  <p><strong>Input and Output:</strong> Users provide a syllabus source (uploaded PDF/TXT, custom excerpt, or indexed public CS syllabus corpus), topic, optional learning outcome, Bloom's level (<em>Remember</em> through <em>Create</em>), question type (<em>Short Answer, Long Answer, MCQ, Numerical</em>), difficulty (<em>Easy, Medium, Hard</em>), quantity, marks per question, and optional exam constraints. The pipeline outputs structured exam questions, syllabus-grounded model answers, stepwise marking rubrics summing strictly to target marks, and a 5-axis quality review (scores 1–5, <code>PASS</code>/<code>REVISE</code> verdict, flagged issues, rewritten question if flawed, and a human-oversight notice).</p>
  <p><strong>How many prompts/steps and why (3 Prompts):</strong> Our final solution uses <strong>3 distinct chained prompts</strong> preceded by Module 1 validation and TF-IDF syllabus retrieval: (1) <strong>P1 Question Generator</strong> synthesizes clean question stems without leaking hints; (2) <strong>P2 Answer Key &amp; Rubric</strong> derives model answers and exact-sum stepwise marking schemes; and (3) <strong>P3 Quality Check Reviewer</strong> acts as an independent critic auditing clarity, syllabus relevance, answerability, Bloom's alignment, and difficulty. Separating generation from grading and moderation prevents answer leakage into stems and stops self-evaluation bias.</p>
  <p><strong>Which tool/model and why:</strong> Built with Python, <strong>Streamlit</strong>, <code>pypdf</code>, and the <code>google-genai</code> SDK calling <strong>Gemini Flash-Lite</strong> (<code>gemini-flash-lite-latest</code> with fallback to <code>gemini-3.5-flash-lite</code>). Live testing showed <code>gemini-2.5-flash</code> returns HTTP 404 for newly provisioned keys and <code>gemini-3-flash</code> enforces a 20 requests/day cap; routing JSON-mode calls across Flash-Lite models with retry/backoff delivers sub-3s latency and resilience against peak-hour HTTP 503 spikes.</p>
  <p><strong>What changed since Milestone 1:</strong> Since Milestone 1, where we proposed a single generation prompt + prose reviewer orchestrated conceptually in Flowise, for Milestone 2 we (1) decomposed generation into separate P1 and P2 prompts, (2) implemented real TF-IDF syllabus chunk retrieval (RAG) supporting PDF uploads and a 7-topic CS corpus, (3) replaced Flowise with a deterministic Python/Streamlit application supporting strict JSON schemas, automatic mark-sum checks, input guardrails, and automated {n12}-case testing, and (4) upgraded the reviewer from unstructured prose to a calibrated 5-axis 1–5 scoring rubric with automatic <code>REVISE</code> rewrites.</p>

  <h2>2(b) Architecture &amp; Workflow Diagrams</h2>
  <div class="diagram-card"><img src="{d1}" alt="Prompt Workflow"/><div class="caption">Figure 2.1: Prompt Workflow — Module 1 validation &amp; RAG retrieval feeding P1 -> P2 -> P3 with rejection short-circuits.</div></div>
  <div class="diagram-card"><img src="{d2}" alt="Task Decomposition"/><div class="caption">Figure 2.2: Task Decomposition — Problem C3 decomposed across four specialized modules.</div></div>
  <div class="diagram-card"><img src="{d3}" alt="Input Output Flow"/><div class="caption">Figure 2.3: Input–Output Data Flow — Structured JSON contracts passed between pipeline stages.</div></div>
  <div class="diagram-card"><img src="{d4}" alt="System Architecture"/><div class="caption">Figure 2.4: System Architecture — Streamlit presentation layer, Python RAG/pipeline controller, and Gemini API layer.</div></div>
  <div class="diagram-card"><img src="{d5}" alt="RAG Pipeline"/><div class="caption">Figure 2.5: Syllabus Grounding (RAG) Pipeline — Chunking, TF-IDF retrieval, context injection, and refusal guardrail.</div></div>

  <h2>2(c) Final Prompt Sheets (Selectable Text)</h2>
  {ps1}
  {ps2}
  {ps3}

  <div class="page-break"></div>

  <!-- SECTION 3 -->
  <h1>3. Implementation</h1>
  <h2>3(a) What Is Built &amp; Module Status Table</h2>
  <p>We built a full end-to-end Streamlit web prototype (<code>code/app.py</code>) backed by modular Python RAG retrieval (<code>code/rag.py</code>), 3-step prompt orchestration (<code>code/pipeline.py</code>), versioned markdown prompt templates (<code>prompts/v1..final</code>), and an automated test harness (<code>code/run_tests.py</code>).</p>
  <table>
    <tr><th>Module</th><th>What it does</th><th>Status</th><th>Notes</th></tr>
    <tr><td><strong>1. Syllabus Grounding (RAG) and Input Validator</strong></td><td>Parses uploaded PDF/TXT or public CS corpus into chunks, retrieves top-2 passages via TF-IDF, and rejects empty, vague, out-of-range, or contradictory inputs.</td><td class="badge-pass">Working</td><td>Verified on Tests 9, 11, 12; zero wasted LLM calls on invalid inputs.</td></tr>
    <tr><td><strong>2. Bloom-Aligned Exam Question Generator (Prompt P1)</strong></td><td>Generates structured exam questions matching target Bloom's cognitive verbs, question type (MCQ/Short/Long/Numerical), and retrieved syllabus scope.</td><td class="badge-pass">Working</td><td>Enforces formal English normalization and out-of-syllabus rejection.</td></tr>
    <tr><td><strong>3. Answer Key and Marking Scheme Generator (Prompt P2)</strong></td><td>Creates syllabus-grounded model answers and observable stepwise marking criteria with deterministic sum verification in Python.</td><td class="badge-pass">Working</td><td>Exact mark totals verified across Normal test cases (Tests 1–7).</td></tr>
    <tr><td><strong>4. Quality Check Reviewer and Revision Engine (Prompt P3)</strong></td><td>Scores each item (1–5) across Clarity, Relevance, Answerability, Bloom's Alignment, and Difficulty; flags REVISE with rewrite and appends faculty approval note.</td><td class="badge-pass">Working</td><td>Detects over-scoped 2-mark mismatches (Test 10) and suggests focused rewrites.</td></tr>
  </table>

  <h2>3(b) Prompt Iteration Log (4 Saved Versions)</h2>
  <table>
    <tr><th>Version</th><th>What changed</th><th>Why it was changed</th><th>Result after the change (Observed on B1–B6)</th></tr>
    <tr><td><strong>v1</strong></td><td>Milestone 1 baseline: single monolithic generation prompt + unstructured prose reviewer.</td><td>Starting baseline from M1 submission.</td><td><strong>0/6 ({s1['json']}) valid JSON</strong>; Bloom drifted on B4 (generated Compare for Evaluate) yet Reviewer stamped Approved; B5 dropped TCP congestion control; B6 wasted a Reviewer call stamping Approved on a refusal.</td></tr>
    <tr><td><strong>v2</strong></td><td>Decomposed generation into P1 + P2; kept P3; added System Roles, strict JSON schemas, and P1 out-of-syllabus refusal rule.</td><td>Unstructured prose broke downstream parsing, caused lenient reviews, and wasted calls on refusals.</td><td><strong>{s2['json']} valid JSON</strong>, <strong>{s2['marks']} mark-sum match</strong>, <strong>{s2['bloom']} Bloom verb match</strong>, B6 rejected cleanly at P1; however P2 returned a bare JSON array on B2 &amp; B3, B1 used Explain instead of Apply verbs, and B3 MCQs omitted A–D options.</td></tr>
    <tr><td><strong>v3</strong></td><td>Added Revised Bloom's verb table, MCQ 4-option rules, few-shot JSON exemplars in P1/P2, and a 5-axis 1–5 scoring rubric + forced REVISE rewrite in P3.</td><td>To eliminate bare-list JSON errors, missing MCQ choices, Bloom verb drift, and rubber-stamp PASS reviews.</td><td><strong>{s3['json']} valid JSON</strong>, <strong>{s3['marks']} mark-sum match</strong>, <strong>{s3['bloom']} Bloom verb match</strong>; MCQs cleanly included options A–D and P3 produced calibrated 1–5 axis scores with actionable REVISE rewrites.</td></tr>
    <tr><td><strong>v4 (final)</strong></td><td>Added strict formal academic English normalization, sub-topic completeness rule, temperature tuning (P1/P2=0.2, P3=0.1), and TF-IDF RAG + deterministic mark check.</td><td>To prevent Hinglish drift or sub-topic omission (B5) and minimize stochastic format variance across full test runs.</td><td><strong>{p12}/{n12} tests passed</strong> on the full {n12}-case evaluation suite (including 1 honest Edge failure on Test 13 synonym retrieval) with exact mark sums, formal English output, clean refusals, and accurate REVISE detection.</td></tr>
  </table>

  <h3>Full Prompt Text of All Recorded Versions (v1 – v4)</h3>
  <p><strong>Version v1 — Baseline Generation &amp; Reviewer Prompts:</strong></p>
  <pre>[v1 P1 Generation]\n{esc(v1_p1['user'])}\n\n[v1 P2 Reviewer]\n{esc(v1_p2['user'])}</pre>
  <p><strong>Version v2 — Decomposed P1, P2, P3 Prompts:</strong></p>
  <pre>[v2 P1 System] {esc(v2_p1['system'])}\n[v2 P1 User]\n{esc(v2_p1['user'])}\n\n[v2 P2 System] {esc(v2_p2['system'])}\n[v2 P2 User]\n{esc(v2_p2['user'])}\n\n[v2 P3 System] {esc(v2_p3['system'])}\n[v2 P3 User]\n{esc(v2_p3['user'])}</pre>
  <p><strong>Version v3 — Bloom Verbs, Few-Shot Exemplars &amp; 5-Axis Rubric:</strong></p>
  <pre>[v3 P1 System] {esc(v3_p1['system'])}\n[v3 P1 User]\n{esc(v3_p1['user'])}\n\n[v3 P2 System] {esc(v3_p2['system'])}\n[v3 P2 User]\n{esc(v3_p2['user'])}\n\n[v3 P3 System] {esc(v3_p3['system'])}\n[v3 P3 User]\n{esc(v3_p3['user'])}</pre>
  <p><strong>Version v4 (Final Production — Prompts P1, P2, P3):</strong></p>
  <pre>[v4 P1 System] {esc(v4_p1['system'])}\n[v4 P1 User]\n{esc(v4_p1['user'])}\n\n[v4 P2 System] {esc(v4_p2['system'])}\n[v4 P2 User]\n{esc(v4_p2['user'])}\n\n[v4 P3 System] {esc(v4_p3['system'])}\n[v4 P3 User]\n{esc(v4_p3['user'])}</pre>

  <div class="page-break"></div>

  <!-- SECTION 4 -->
  <h1>4. Demonstration and testing</h1>
  <h2>4(a) {n12}-Case Evaluation Test Table</h2>
  <table>
    <tr><th>Test no.</th><th>Input (short)</th><th>Type</th><th>Expected output</th><th>Actual output (short)</th><th>Pass / Fail</th></tr>
    {test_rows_html}
  </table>

  <h2>4(b) Captioned Screenshots of Real Runs</h2>
  {sc_block(sc_test1, "Screenshot 1 (Test 1 — Normal): BST Deletion & Inorder Traversal (Apply, Short Answer, 2x5M) showing P1/P2/P3 metrics and PASS verdict.")}
  {sc_block(sc_test10, "Screenshot 2 (Test 10 — Edge): Broad OS Scheduling syllabus scoped to 2 marks — P3 flags REVISE (low answerability/difficulty calibration) with focused rewrite.")}
  {sc_block(sc_test11, "Screenshot 3 (Test 11 — Invalid): Topic 'idk' caught and rejected cleanly by Module 1 Input Validator before invoking Gemini.")}

  <h2>4(c) Known Limitations &amp; Next Steps (Milestone 3)</h2>
  <ul>
    <li><strong>Lexical RAG Matching Limits:</strong> Current TF-IDF retrieval relies on keyword overlap and can miss paraphrased conceptual queries. <em>Next:</em> Add dense semantic embeddings (<code>gemini-embedding-001</code>) hybrid search over uploaded course PDFs.</li>
    <li><strong>Single-Pass Reviewer Score Variance:</strong> A single call to P3 can still vary by ±1 point on borderline difficulty judgments. <em>Next:</em> Implement 3-run self-consistency voting for P3 moderation scores.</li>
    <li><strong>Free-Tier Peak Latency &amp; 503 Spikes:</strong> Public free-tier Gemini endpoints experience transient HTTP 503 load spikes requiring multi-model retries. <em>Next:</em> Support configurable backup providers/keys and async progress streaming.</li>
    <li><strong>STEM Diagram &amp; LaTeX Rendering:</strong> Generated BST/scheduling questions return text descriptions rather than visual diagrams or rendered PDF exam sheets. <em>Next:</em> Add printable PDF/DOCX question-paper export and Mermaid/SVG diagram generation.</li>
  </ul>

  <div class="page-break"></div>

  <!-- SECTION 5 -->
  <h1>5. Repository</h1>
  {sc_block(sc_repo, "GitHub Repository Screenshot: jayantkriplani0-crypto/AssessMate-PE-B65-48 showing Milestone 2 folder layout and commit history.")}
  <p><strong>What Changed Since Milestone 1:</strong> Since submitting our Milestone 1 baseline prompt (<code>prompts/v1/</code>), we evolved the repository through dated commits across <code>v2</code> (task decomposition into P1/P2/P3 JSON schemas), <code>v3</code> (Bloom's cognitive verb table, MCQ formatting rules, few-shot exemplars, and 5-axis 1–5 reviewer rubric), and <code>v4/final</code> (formal English guardrails and refusal checks). We also implemented the TF-IDF syllabus RAG module (<code>code/rag.py</code>), 3-prompt chaining engine (<code>code/pipeline.py</code>), interactive Streamlit prototype (<code>code/app.py</code>), {n12}-case test suite (<code>test-data/</code>), five architecture diagrams (<code>docs/diagrams/</code>), and dated progress entries in <code>CHANGELOG.md</code> with zero API keys committed.</p>

  <div class="page-break"></div>

  <!-- SECTION 6 -->
  <h1>6. Supporting document</h1>
  <div class="box"><em>Attached below is the identical Technical Report uploaded separately at Form Q16 (<code>BEYOND_THE_PROMPT_TechnicalReport.pdf</code>).</em></div>
  {tech_body}

  <div class="page-break"></div>

  <!-- SECTION 7 -->
  <h1>7. Team contribution</h1>
  <p>All three team members contributed to design, prompt iteration, implementation, testing, and documentation, and mutually agreed to the contribution breakdown below:</p>
  <table>
    <tr>
      <th>Member name</th>
      <th>Enrollment no.</th>
      <th>Role</th>
      <th>Tasks done in Milestone 2</th>
      <th>Evidence</th>
      <th>Contribution (%)</th>
    </tr>
    <tr>
      <td>Jayant Kriplani</td>
      <td><code>S24CSEU2763</code></td>
      <td>Architecture, App &amp; Deployment Lead</td>
      <td>Built 3-step chaining engine (<code>pipeline.py</code>), TF-IDF RAG grounding (<code>rag.py</code>), Streamlit web app (<code>app.py</code>), deployed prototype on Streamlit Cloud, recorded and uploaded 141s demo reel.</td>
      <td><code>code/rag.py</code>, <code>code/pipeline.py</code>, <code>code/app.py</code>, live Streamlit URL, commits <code>1bf828a</code>, <code>211541d</code>, Demo Reel</td>
      <td>40</td>
    </tr>
    <tr>
      <td>Shubham Mittal</td>
      <td><code>S24CSEU2764</code></td>
      <td>Prompt Design &amp; Iteration Lead</td>
      <td>Designed and iterated prompts <code>v1</code>–<code>v4</code> (P1 Generator, P2 Answer Key &amp; Rubric, P3 Quality Reviewer), Bloom's action-verb constraints, few-shot JSON exemplars, and 5-axis 1–5 moderation rubric.</td>
      <td><code>prompts/v1/</code>–<code>prompts/final/</code> (<code>P1</code>–<code>P3</code>), Section 2(c) Prompt Sheets, Section 3 Iteration Log, commits <code>d4797b4</code>, <code>77599f6</code>, <code>7e384b5</code></td>
      <td>30</td>
    </tr>
    <tr>
      <td>Ajay Chopra</td>
      <td><code>S24CSEU2827</code></td>
      <td>Testing, Diagrams &amp; Documentation Lead</td>
      <td>Curated public CS syllabus corpus, built and evaluated 13-case test suite, drew 5 original workflow/architecture/RAG SVG diagrams, drafted Technical Report and Milestone 2 documentation.</td>
      <td><code>test-data/cs_syllabus_corpus.json</code>, <code>code/run_tests.py</code>, <code>test-data/test_results.md</code>, <code>docs/diagrams/*.svg</code>, Section 4 &amp; Section 6</td>
      <td>30</td>
    </tr>
    <tr>
      <td colspan="5" style="text-align:right;"><strong>Total Contribution</strong></td>
      <td><strong>100%</strong></td>
    </tr>
  </table>
</body>
</html>
"""
    m2_html_path = ROOT / "docs" / "_m2_report.html"
    m2_html_path.write_text(m2_html, encoding="utf-8")

    browser = CHROME_EXE if CHROME_EXE.exists() else EDGE_EXE
    sub_dir = ROOT / "submission"
    sub_dir.mkdir(exist_ok=True)

    tech_pdf_docs = ROOT / "docs" / "BEYOND_THE_PROMPT_TechnicalReport.pdf"
    tech_pdf_sub = sub_dir / "BEYOND_THE_PROMPT_TechnicalReport.pdf"
    m2_pdf_docs = ROOT / "docs" / "M2_PE-B65-48_AssessMate.pdf"
    m2_pdf_sub = sub_dir / "M2_PE-B65-48_AssessMate.pdf"

    import tempfile
    with tempfile.TemporaryDirectory() as prof:
        for html_src, pdf_dst in [(tech_html_path, tech_pdf_docs), (m2_html_path, m2_pdf_docs)]:
            subprocess.run(
                [
                    str(browser),
                    "--headless=new",
                    "--disable-gpu",
                    f"--user-data-dir={prof}",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_dst}",
                    html_src.as_uri(),
                ],
                check=True,
            )

    tech_pdf_sub.write_bytes(tech_pdf_docs.read_bytes())
    m2_pdf_sub.write_bytes(m2_pdf_docs.read_bytes())
    tech_html_path.unlink(missing_ok=True)
    m2_html_path.unlink(missing_ok=True)
    print(f"Built Technical Report ({tech_pdf_docs.stat().st_size // 1024} KB) and M2 PDF ({m2_pdf_docs.stat().st_size // 1024} KB).")


if __name__ == "__main__":
    main()
