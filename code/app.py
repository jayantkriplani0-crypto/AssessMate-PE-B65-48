"""AssessMate Streamlit Web Application (SCSE4041 Mini Project — Problem C3, Team PE-B65-48)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from pipeline import (
    BLOOM_LEVELS,
    DIFFICULTIES,
    QUESTION_TYPES,
    AssessmentRequest,
    load_api_key,
    run_assessmate_pipeline,
)
from rag import extract_text_from_pdf, load_default_syllabus_chunks

ROOT = Path(__file__).resolve().parents[1]

SAMPLE_PRESETS: dict[str, dict[str, object]] = {
    "Custom Input": {},
    "Normal: BST Deletion & Inorder (Apply)": {
        "topic": "Binary Search Trees: deletion and inorder traversal",
        "learning_outcome": "Perform deletion cases and inorder traversal on a Binary Search Tree.",
        "bloom": "Apply",
        "qtype": "Short Answer",
        "diff": "Medium",
        "n": 2,
        "marks": 5,
        "constraints": "Closed-book written exam; require step-by-step tracing.",
    },
    "Normal: DBMS Normalization BCNF (Analyze)": {
        "topic": "DBMS Normalization up to BCNF",
        "learning_outcome": "Identify anomalies and decompose relations up to 3NF and BCNF.",
        "bloom": "Analyze",
        "qtype": "Long Answer",
        "diff": "Hard",
        "n": 1,
        "marks": 5,
        "constraints": "Include anomaly identification and lossless-join check.",
    },
    "Normal: REST HTTP Idempotency (Understand MCQ)": {
        "topic": "HTTP Methods and REST API Idempotency",
        "learning_outcome": "Differentiate GET, PUT, POST, and PATCH semantics.",
        "bloom": "Understand",
        "qtype": "MCQ",
        "diff": "Easy",
        "n": 2,
        "marks": 2,
        "constraints": "4 options (A-D) per MCQ.",
    },
    "Edge: Broad Syllabus for 2 Marks": {
        "topic": "Complete Operating Systems CPU Scheduling including FCFS, SJF, and Round Robin mathematical tradeoffs",
        "learning_outcome": "Compare scheduling algorithms across multiple metrics.",
        "bloom": "Create",
        "qtype": "Long Answer",
        "diff": "Hard",
        "n": 1,
        "marks": 2,
        "constraints": "Strictly 2-mark short question.",
    },
    "Edge: Out-of-Syllabus Topic (RAG Refusal)": {
        "topic": "Quantum Shor Factorization Algorithm",
        "learning_outcome": "Explain modular period finding.",
        "bloom": "Apply",
        "qtype": "Short Answer",
        "diff": "Hard",
        "n": 1,
        "marks": 5,
        "constraints": "Use only supplied CS syllabus.",
    },
    "Invalid: Vague Topic ('idk')": {
        "topic": "idk",
        "learning_outcome": "",
        "bloom": "Apply",
        "qtype": "Short Answer",
        "diff": "Medium",
        "n": 2,
        "marks": 5,
        "constraints": "None",
    },
}


def _resolve_key(sidebar_key: str) -> str:
    if sidebar_key.strip():
        return sidebar_key.strip()
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
        if secret_key:
            return str(secret_key).strip()
    except Exception:  # noqa: BLE001
        pass
    return load_api_key()


def _format_exam_markdown(res: dict) -> str:
    req = res["request"]
    questions = res["p1_output"].get("questions", [])
    sols = {s["id"]: s for s in res["p2_output"].get("solutions", [])}
    revs = {r["id"]: r for r in res["p3_output"].get("reviews", [])}
    lines = [
        f"# AssessMate Exam Paper & Moderation Pack",
        f"- **Topic:** {req['topic']}",
        f"- **Bloom's Level:** {req['bloom_level']} | **Type:** {req['question_type']} | **Difficulty:** {req['difficulty']}",
        "",
    ]
    for q in questions:
        sol = sols.get(q["id"], {})
        rev = revs.get(q["id"], {})
        lines.append(f"## {q['id']} ({q['marks']} Marks · {q['bloom_level']})")
        lines.append(q["question_text"])
        lines.append("")
        lines.append(f"**Model Answer:** {sol.get('model_answer', '')}")
        lines.append("**Marking Scheme:**")
        for c in sol.get("marking_scheme", []):
            lines.append(f"- {c['criterion']} ({c['marks']} marks)")
        lines.append(f"**Quality Review Verdict:** {rev.get('verdict', 'N/A')} ({rev.get('overall_score', '-')}/5)")
        lines.append("")
    lines.append("---")
    lines.append("*Human Oversight Note: AI-generated assessment material requires final teacher verification before exam use.*")
    return "\n".join(lines)


st.set_page_config(
    page_title="AssessMate | Exam Question Generator & Quality Check",
    page_icon="📝",
    layout="wide",
)

st.title("AssessMate: Exam Question Generator with Quality Check")
st.caption(
    "SCSE4041 Prompt Engineering Mini Project (Problem C3) · Team PE-B65-48 (BEYOND THE PROMPT) · "
    "RAG Syllabus Grounding + 3-Step Chained Pipeline (P1 -> P2 -> P3)"
)

with st.sidebar:
    st.header("Configuration")
    sidebar_api_key = st.text_input(
        "Gemini API Key (optional if configured)",
        type="password",
        value="",
        help="Uses Streamlit Secrets / environment key by default, or enter your own Google AI Studio key.",
    )
    active_key = _resolve_key(sidebar_api_key)
    if active_key:
        st.success("API Status: Live Gemini Key Configured")
    else:
        st.warning("No API key found. Enter a Gemini API key above to execute.")

    st.divider()
    st.subheader("Working Modules")
    st.markdown(
        "1. Syllabus Grounding (RAG) and Input Validator\n"
        "2. Bloom-Aligned Exam Question Generator (P1)\n"
        "3. Answer Key and Marking Scheme Generator (P2)\n"
        "4. Quality Check Reviewer and Revision Engine (P3)"
    )

    st.divider()
    qp = st.query_params
    qp_preset = qp.get("preset", "")
    preset_keys = list(SAMPLE_PRESETS.keys())
    default_preset_idx = preset_keys.index(qp_preset) if qp_preset in preset_keys else 0
    preset_name = st.selectbox("Load Sample Test Preset", preset_keys, index=default_preset_idx)
    preset = SAMPLE_PRESETS[preset_name]

    st.divider()
    st.subheader("Bloom's Cognitive Verbs")
    for lvl, verbs in BLOOM_LEVELS.items():
        st.markdown(f"**{lvl}:** {', '.join(verbs[:4])}")

col_left, col_right = st.columns([1.15, 1.85], gap="large")

with col_left:
    st.subheader("1. Syllabus & Assessment Parameters")
    syllabus_source = st.radio(
        "Syllabus Source",
        ["Standard Public CS Syllabus Corpus (RAG)", "Paste Custom Syllabus Text", "Upload Syllabus PDF/TXT"],
        horizontal=False,
    )
    custom_syllabus = ""
    if syllabus_source == "Paste Custom Syllabus Text":
        custom_syllabus = st.text_area(
            "Syllabus Excerpt",
            height=130,
            placeholder="Paste syllabus notes or course text here...",
        )
    elif syllabus_source == "Upload Syllabus PDF/TXT":
        uploaded = st.file_uploader("Upload PDF or TXT", type=["pdf", "txt", "md"])
        if uploaded is not None:
            raw_bytes = uploaded.read()
            if uploaded.name.lower().endswith(".pdf"):
                custom_syllabus = extract_text_from_pdf(raw_bytes)
            else:
                custom_syllabus = raw_bytes.decode("utf-8", errors="ignore")
            st.caption(f"Extracted {len(custom_syllabus.split())} words from `{uploaded.name}`.")
    else:
        topics_list = [f"{c['subject']}: {c['topic']}" for c in load_default_syllabus_chunks()]
        st.caption("Indexed CS topics: " + " · ".join(topics_list[:4]) + " (+3 more)")

    with st.form("assessmate_form"):
        topic_val = str(preset.get("topic", "Binary Search Trees: deletion and inorder traversal"))
        lo_val = str(preset.get("learning_outcome", "Apply BST deletion rules and trace inorder traversal."))
        bloom_default = str(preset.get("bloom", "Apply"))
        qtype_default = str(preset.get("qtype", "Short Answer"))
        diff_default = str(preset.get("diff", "Medium"))
        n_default = int(preset.get("n", 2))
        m_default = int(preset.get("marks", 5))
        const_default = str(preset.get("constraints", "Closed-book written exam; require step-by-step reasoning."))

        topic = st.text_input("Syllabus Topic", value=topic_val)
        learning_outcome = st.text_input("Learning Outcome (optional)", value=lo_val)

        c1, c2 = st.columns(2)
        with c1:
            bloom_level = st.selectbox("Bloom's Taxonomy Level", list(BLOOM_LEVELS.keys()), index=list(BLOOM_LEVELS.keys()).index(bloom_default))
            question_type = st.selectbox("Question Type", QUESTION_TYPES, index=QUESTION_TYPES.index(qtype_default))
            num_questions = st.number_input("Quantity", min_value=0, max_value=10, value=n_default)
        with c2:
            difficulty = st.selectbox("Difficulty", DIFFICULTIES, index=DIFFICULTIES.index(diff_default))
            marks_per_question = st.number_input("Marks per Question", min_value=1, max_value=20, value=m_default)

        constraints = st.text_input("Additional Constraints", value=const_default)
        run_btn = st.form_submit_button("Run 3-Step Prompt Pipeline", type="primary", use_container_width=True)

auto_key = f"autorun_{qp_preset}"
should_autorun = qp.get("autorun") == "1" and qp_preset in SAMPLE_PRESETS and not st.session_state.get(auto_key)
if run_btn or should_autorun:
    if should_autorun:
        st.session_state[auto_key] = True
    req = AssessmentRequest(
        topic=topic,
        bloom_level=bloom_level,
        question_type=question_type,
        difficulty=difficulty,
        num_questions=int(num_questions),
        marks_per_question=int(marks_per_question),
        learning_outcome=learning_outcome,
        constraints=constraints,
        syllabus_text=custom_syllabus,
    )
    with st.spinner("Retrieving syllabus passages and running P1 -> P2 -> P3..."):
        try:
            st.session_state["last_result"] = run_assessmate_pipeline(req, api_key=active_key)
        except Exception as exc:  # noqa: BLE001
            st.session_state["last_result"] = {"status": "ERROR", "error": str(exc)}

with col_right:
    st.subheader("2. Generated Output & Quality Audit")
    res = st.session_state.get("last_result")
    if not res:
        st.info("Configure inputs on the left (or select a preset) and click **Run 3-Step Prompt Pipeline**.")
    elif res.get("status") == "ERROR":
        st.error(f"Execution Error: {res.get('error')}")
    elif res.get("status") == "REJECTED":
        st.error(f"Request Rejected at {res.get('rejected_stage')}")
        for err in res.get("validation_errors", []):
            st.warning(err)
        chunks = res.get("rag_context", {}).get("retrieved_chunks", [])
        if chunks:
            with st.expander("Retrieved Syllabus Passages Checked"):
                for ch in chunks:
                    st.markdown(f"**{ch['chunk_id']} ({ch['subject']})** — Relevance Score: `{ch['score']}`")
                    st.caption(ch["text"])
    else:
        questions = res["p1_output"].get("questions", [])
        solutions = {s["id"]: s for s in res["p2_output"].get("solutions", [])}
        reviews = {r["id"]: r for r in res["p3_output"].get("reviews", [])}
        summary = res["p3_output"].get("summary", {})
        marks_ok_count = sum(1 for q in questions if solutions.get(q["id"], {}).get("marks_sum_valid"))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Questions (P1)", len(questions))
        m2.metric("Mark Sums Valid", f"{marks_ok_count}/{len(questions)}")
        m3.metric("Reviewer PASS", f"{summary.get('passed', 0)}/{summary.get('total_reviewed', len(questions))}")
        m4.metric("Avg Quality Score", f"{summary.get('average_quality_score', '-')} / 5")

        tabs = [
            "Questions (P1)",
            "Answer Keys & Rubrics (P2)",
            "Quality Review (P3)",
            "RAG Context & Prompts",
            "Export",
        ]
        qp_tab = st.query_params.get("tab", "Questions (P1)")
        tab_idx = tabs.index(qp_tab) if qp_tab in tabs else 0
        active_tab = st.radio("Output View", tabs, index=tab_idx, horizontal=True, label_visibility="collapsed")

        if active_tab == "Questions (P1)":
            for q in questions:
                with st.container(border=True):
                    st.markdown(
                        f"**{q['id']}** · Type: `{q.get('question_type', '-')}` · Bloom: `{q.get('bloom_level', '-')}` · "
                        f"Verb: `{q.get('action_verb', '-')}` · Marks: `{q.get('marks', '-')}`"
                    )
                    st.write(q.get("question_text", ""))
                    if q.get("options"):
                        for opt in q["options"]:
                            st.markdown(f"- {opt}")

        elif active_tab == "Answer Keys & Rubrics (P2)":
            for q in questions:
                sol = solutions.get(q["id"], {})
                with st.container(border=True):
                    st.markdown(f"**{q['id']} Model Answer**")
                    st.write(sol.get("model_answer", ""))
                    st.markdown("**Stepwise Marking Scheme:**")
                    for step in sol.get("marking_scheme", []):
                        st.markdown(f"- {step['criterion']} — **{step['marks']} marks**")
                    sum_ok = sol.get("marks_sum_valid", False)
                    st.caption(
                        f"Verified Sum: {sol.get('computed_marks_sum', 0)} / {q.get('marks', 0)} "
                        + ("(Exact Match)" if sum_ok else "(Mismatch Detected)")
                    )

        elif active_tab == "Quality Review (P3)":
            for q in questions:
                rev = reviews.get(q["id"], {})
                verdict = rev.get("verdict", "REVISE")
                with st.container(border=True):
                    hdr = f"**{q['id']} Verdict:** `{verdict}` · Overall Score: `{rev.get('overall_score', '-')}/5.0`"
                    if verdict == "PASS":
                        st.success(hdr)
                    else:
                        st.warning(hdr)
                    sc = rev.get("scores", {})
                    st.write(
                        f"Clarity: **{sc.get('clarity', '-')}** | "
                        f"Syllabus Relevance: **{sc.get('syllabus_relevance', '-')}** | "
                        f"Answerability: **{sc.get('answerability', '-')}** | "
                        f"Bloom Alignment: **{sc.get('bloom_alignment', '-')}** | "
                        f"Difficulty: **{sc.get('difficulty', '-')}**"
                    )
                    if rev.get("issues"):
                        st.markdown("**Flagged Issues:**")
                        for issue in rev["issues"]:
                            st.markdown(f"- {issue}")
                    if rev.get("revised_question"):
                        st.info(f"**Suggested Revision:** {rev['revised_question']}")
            st.info(
                res["p3_output"].get(
                    "human_oversight_note",
                    "Human Oversight: A faculty reviewer must verify final generated questions and marking schemes prior to exam use.",
                )
            )

        elif active_tab == "RAG Context & Prompts":
            st.markdown("**Retrieved Syllabus Passages (RAG Grounding)**")
            for ch in res["rag_context"].get("retrieved_chunks", []):
                with st.container(border=True):
                    st.markdown(f"**{ch['chunk_id']} | {ch['subject']} — {ch['topic']}** (Score: `{ch['score']}`)")
                    st.write(ch["text"])
            st.markdown("**Models Used:** " + json.dumps(res.get("models_used", {})))
            for pid in ("P1", "P2", "P3"):
                with st.expander(f"Rendered Prompt {pid}"):
                    st.code(res["prompts"].get(pid, ""), language="text")

        else:
            st.download_button(
                "Download Full JSON Output",
                data=json.dumps(res, indent=2, ensure_ascii=False),
                file_name="assessmate_output.json",
                mime="application/json",
                use_container_width=True,
            )
            st.download_button(
                "Download Exam & Rubric (Markdown)",
                data=_format_exam_markdown(res),
                file_name="assessmate_exam_pack.md",
                mime="text/markdown",
                use_container_width=True,
            )
