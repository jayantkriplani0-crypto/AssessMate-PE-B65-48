"""AssessMate 3-Prompt Chained Pipeline with Syllabus Grounding (RAG).

Modules:
  1. Syllabus Grounding (RAG) & Input Validator (`rag.py`)
  2. Bloom-Aligned Exam Question Generator (`P1`)
  3. Answer Key & Stepwise Marking Scheme Generator (`P2`)
  4. Independent Quality Check Reviewer & Revision Engine (`P3`)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from rag import (
    BLOOM_LEVELS,
    DIFFICULTIES,
    QUESTION_TYPES,
    AssessmentRequest,
    build_grounded_context,
    validate_request,
)

ROOT = Path(__file__).resolve().parents[1]
FINAL_PROMPTS_DIR = ROOT / "prompts" / "final"
FALLBACK_MODELS = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite"]


def load_api_key(explicit_key: str | None = None) -> str:
    """Resolve Gemini API key from explicit input, environment, or gitignored .env."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def parse_prompt_markdown(path: Path) -> tuple[str, str]:
    """Extract (system_prompt, user_template) from a prompt markdown file."""
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"## System Prompt\s*\n(.*?)\n## User Prompt Template\s*\n(.*)\Z",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError(f"Could not parse System/User prompt sections from {path}")
    return match.group(1).strip(), match.group(2).strip()


def load_final_prompts() -> dict[str, tuple[str, str]]:
    """Load the final production prompt templates (P1, P2, P3)."""
    return {
        "P1": parse_prompt_markdown(FINAL_PROMPTS_DIR / "P1_question_generator.md"),
        "P2": parse_prompt_markdown(FINAL_PROMPTS_DIR / "P2_answer_key_rubric.md"),
        "P3": parse_prompt_markdown(FINAL_PROMPTS_DIR / "P3_quality_reviewer.md"),
    }


def render_template(template: str, variables: dict[str, Any]) -> str:
    """Safely substitute {key} placeholders without touching JSON curly braces."""
    rendered = template
    for key, val in variables.items():
        rendered = rendered.replace("{" + key + "}", str(val))
    return rendered


def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _call_gemini_json(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> tuple[dict[str, Any], str]:
    """Call Gemini Flash-Lite models with automatic retry and fallback on 503 spikes."""
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=25000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    cfg = types.GenerateContentConfig(
        system_instruction=system_prompt if system_prompt.lower() != "none" else None,
        temperature=temperature,
        top_p=0.9,
        max_output_tokens=2048,
        response_mime_type="application/json",
    )

    last_err: Exception | None = None
    for attempt in range(6):
        saw_429 = False
        for model_name in FALLBACK_MODELS:
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=cfg,
                )
                time.sleep(1.2)
                return _extract_json(resp.text or "{}"), model_name
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if "429" in str(exc):
                    saw_429 = True
                time.sleep(1.5)
        time.sleep(10.0 if saw_429 else 2.5)
    raise RuntimeError(f"Gemini API call failed across fallback models: {last_err}")


def render_all_prompts(
    req: AssessmentRequest,
    syllabus_excerpt: str,
    questions_json: str = "[]",
    package_json: str = "{}",
) -> dict[str, str]:
    """Render P1, P2, P3 user prompts for inspection and export."""
    templates = load_final_prompts()
    base_vars = {
        "syllabus_excerpt": syllabus_excerpt,
        "topic": req.topic.strip(),
        "learning_outcome": req.learning_outcome.strip() or "Demonstrate conceptual and applied mastery.",
        "bloom_level": req.bloom_level,
        "question_type": req.question_type,
        "difficulty": req.difficulty,
        "num_questions": req.num_questions,
        "marks_per_question": req.marks_per_question,
        "constraints": req.constraints.strip() or "None",
        "questions_json": questions_json,
        "package_json": package_json,
    }
    return {pid: render_template(usr_tmpl, base_vars) for pid, (_, usr_tmpl) in templates.items()}


def run_assessmate_pipeline(req: AssessmentRequest, api_key: str | None = None) -> dict[str, Any]:
    """Execute Modules 1 -> 2 (P1) -> 3 (P2) -> 4 (P3) sequentially."""
    # Module 1A: Input & constraint validation
    is_valid, validation_errors = validate_request(req)
    # Module 1B: Syllabus grounding (RAG retrieval)
    rag_ctx = build_grounded_context(req, top_k=2)
    excerpt = rag_ctx["syllabus_excerpt"]

    if not is_valid:
        return {
            "status": "REJECTED",
            "rejected_stage": "Module 1 (Input Validator)",
            "validation_errors": validation_errors,
            "request": asdict(req),
            "rag_context": rag_ctx,
            "models_used": {},
            "prompts": {},
            "p1_output": {"status": "REJECTED", "reason": "; ".join(validation_errors), "questions": []},
            "p2_output": {"solutions": []},
            "p3_output": {"reviews": [], "summary": {"total_reviewed": 0, "passed": 0, "needs_revision": 0, "average_quality_score": 0.0}},
        }

    key = load_api_key(api_key)
    if not key:
        raise ValueError("Missing Gemini API key. Enter a valid key in the sidebar or configure GEMINI_API_KEY.")

    templates = load_final_prompts()
    p1_sys, _ = templates["P1"]
    p2_sys, _ = templates["P2"]
    p3_sys, _ = templates["P3"]

    # Module 2: P1 Question Generator
    prompts_step1 = render_all_prompts(req, excerpt)
    p1_out, m1 = _call_gemini_json(key, p1_sys, prompts_step1["P1"], temperature=0.2)

    if p1_out.get("status") == "REJECTED" or not p1_out.get("questions"):
        reason = p1_out.get("reason", "Topic is not covered in the supplied syllabus context.")
        return {
            "status": "REJECTED",
            "rejected_stage": "Module 2 (P1 Grounding Guardrail)",
            "validation_errors": [reason],
            "request": asdict(req),
            "rag_context": rag_ctx,
            "models_used": {"P1": m1},
            "prompts": prompts_step1,
            "p1_output": p1_out,
            "p2_output": {"solutions": []},
            "p3_output": {"reviews": [], "summary": {"total_reviewed": 0, "passed": 0, "needs_revision": 0, "average_quality_score": 0.0}},
        }

    # Module 3: P2 Answer Key & Stepwise Marking Scheme
    q_json = json.dumps(p1_out["questions"], indent=2)
    prompts_step2 = render_all_prompts(req, excerpt, questions_json=q_json)
    p2_out, m2 = _call_gemini_json(key, p2_sys, prompts_step2["P2"], temperature=0.2)

    # Deterministic check on marking scheme sums
    for sol in p2_out.get("solutions", []):
        scheme_sum = round(sum(float(item.get("marks", 0)) for item in sol.get("marking_scheme", [])), 2)
        sol["computed_marks_sum"] = scheme_sum
        sol["marks_sum_valid"] = abs(scheme_sum - float(req.marks_per_question)) < 1e-6

    # Module 4: P3 Quality Check Reviewer
    pkg_json = json.dumps({"questions": p1_out["questions"], "solutions": p2_out.get("solutions", [])}, indent=2)
    prompts_all = render_all_prompts(req, excerpt, questions_json=q_json, package_json=pkg_json)
    p3_out, m3 = _call_gemini_json(key, p3_sys, prompts_all["P3"], temperature=0.1)

    return {
        "status": "OK",
        "rejected_stage": None,
        "validation_errors": [],
        "request": asdict(req),
        "rag_context": rag_ctx,
        "models_used": {"P1": m1, "P2": m2, "P3": m3},
        "prompts": prompts_all,
        "p1_output": p1_out,
        "p2_output": p2_out,
        "p3_output": p3_out,
    }
