"""Evaluate AssessMate prompt versions (v1 through v4) against CS syllabus benchmarks."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parents[1]
FALLBACK_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
]

BLOOM_VERBS: dict[str, set[str]] = {
    "Remember": {"define", "list", "recall", "state", "identify", "name", "mention"},
    "Understand": {"explain", "summarize", "classify", "compare", "interpret", "describe", "distinguish"},
    "Apply": {"compute", "trace", "implement", "solve", "demonstrate", "apply", "calculate", "construct", "use"},
    "Analyze": {"differentiate", "examine", "diagnose", "decompose", "contrast", "analyze", "analyse", "investigate"},
    "Evaluate": {"critique", "justify", "assess", "recommend", "prioritize", "evaluate", "defend", "argue"},
    "Create": {"design", "formulate", "construct", "synthesize", "propose", "architect", "develop"},
}

HINGLISH_MARKERS = {"samjhao", "banao", "kya", "kaise", "aur", "liye", "pe", "bhai", "karo", "hai"}


def load_env_key() -> str:
    """Read GEMINI_API_KEY from environment or gitignored .env file."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("GEMINI_API_KEY not found in environment or .env")


def make_client(api_key: str) -> genai.Client:
    """Create a fast-failing Gemini client so fallback triggers promptly."""
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=25000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def generate_with_fallback(
    client: genai.Client,
    contents: str,
    system_instruction: str | None = None,
    temperature: float | None = None,
    json_mode: bool = False,
) -> tuple[str, str]:
    """Call Flash-Lite/Flash models with polite pacing and fallback on 503/429."""
    cfg_kwargs: dict[str, Any] = {"max_output_tokens": 1800}
    if system_instruction and system_instruction.lower() != "none":
        cfg_kwargs["system_instruction"] = system_instruction
    if temperature is not None:
        cfg_kwargs["temperature"] = temperature
    if json_mode:
        cfg_kwargs["response_mime_type"] = "application/json"
    cfg = types.GenerateContentConfig(**cfg_kwargs)

    last_err: Exception | None = None
    for attempt in range(8):
        for model_name in FALLBACK_MODELS:
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=cfg,
                )
                time.sleep(0.8)
                return (resp.text or ""), model_name
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                print(f"    [round {attempt+1}] {model_name}: {str(exc)[:80]}", flush=True)
                time.sleep(0.8)
        time.sleep(1.5)
    raise RuntimeError(f"All fallback Gemini models failed: {last_err}")


def parse_prompt_markdown(path: Path) -> tuple[str, str]:
    """Extract (system_prompt, user_template) from a versioned prompt markdown file."""
    text = path.read_text(encoding="utf-8")
    sys_match = re.search(
        r"## System Prompt\s*\n(.*?)\n## User Prompt Template\s*\n(.*)\Z",
        text,
        flags=re.DOTALL,
    )
    if not sys_match:
        raise ValueError(f"Invalid prompt markdown format in {path}")
    return sys_match.group(1).strip(), sys_match.group(2).strip()


def load_corpus() -> dict[str, dict[str, str]]:
    items = json.loads((ROOT / "test-data" / "cs_syllabus_corpus.json").read_text(encoding="utf-8"))
    return {item["chunk_id"]: item for item in items}


def benchmark_cases(corpus: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """Six CS benchmark inputs spanning normal, edge, and out-of-syllabus conditions."""
    return [
        {
            "case_id": "B1",
            "syllabus_excerpt": corpus["CS-DSA-01"]["text"],
            "topic": "Binary Search Trees: deletion and inorder traversal",
            "learning_outcome": corpus["CS-DSA-01"]["learning_outcome"],
            "bloom_level": "Apply",
            "difficulty": "Medium",
            "question_type": "Short Answer",
            "num_questions": 2,
            "marks_per_question": 5,
            "note": "Normal CS Apply case",
        },
        {
            "case_id": "B2",
            "syllabus_excerpt": corpus["CS-DBMS-01"]["text"],
            "topic": "DBMS Normalization up to BCNF",
            "learning_outcome": corpus["CS-DBMS-01"]["learning_outcome"],
            "bloom_level": "Analyze",
            "difficulty": "Hard",
            "question_type": "Long Answer",
            "num_questions": 1,
            "marks_per_question": 5,
            "note": "Normal Analyze case",
        },
        {
            "case_id": "B3",
            "syllabus_excerpt": corpus["CS-CN-02"]["text"],
            "topic": "HTTP Methods and REST Idempotency",
            "learning_outcome": corpus["CS-CN-02"]["learning_outcome"],
            "bloom_level": "Understand",
            "difficulty": "Easy",
            "question_type": "MCQ",
            "num_questions": 2,
            "marks_per_question": 2,
            "note": "Normal MCQ case",
        },
        {
            "case_id": "B4",
            "syllabus_excerpt": corpus["CS-OS-01"]["text"],
            "topic": "CPU Scheduling (FCFS, SJF, Round Robin)",
            "learning_outcome": corpus["CS-OS-01"]["learning_outcome"],
            "bloom_level": "Evaluate",
            "difficulty": "Medium",
            "question_type": "Short Answer",
            "num_questions": 1,
            "marks_per_question": 4,
            "note": "Higher-order Evaluate case",
        },
        {
            "case_id": "B5",
            "syllabus_excerpt": corpus["CS-CN-01"]["text"],
            "topic": "TCP Congestion Control samjhao aur 3-way handshake pe question banao",
            "learning_outcome": corpus["CS-CN-01"]["learning_outcome"],
            "bloom_level": "Understand",
            "difficulty": "Medium",
            "question_type": "Short Answer",
            "num_questions": 1,
            "marks_per_question": 5,
            "note": "Edge: Hinglish informal prompt",
        },
        {
            "case_id": "B6",
            "syllabus_excerpt": corpus["CS-DSA-01"]["text"],
            "topic": "Quantum Shor Factorization Algorithm",
            "learning_outcome": "Explain modular period finding in Shor's algorithm.",
            "bloom_level": "Apply",
            "difficulty": "Hard",
            "question_type": "Short Answer",
            "num_questions": 1,
            "marks_per_question": 5,
            "note": "Edge: Topic completely absent from supplied syllabus excerpt",
        },
    ]


def _extract_json_obj(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def render_template(template: str, variables: dict[str, Any]) -> str:
    """Safely substitute {key} placeholders without breaking JSON schema curly braces."""
    rendered = template
    for key, val in variables.items():
        rendered = rendered.replace("{" + key + "}", str(val))
    return rendered


def run_chained_version(
    client: genai.Client,
    version_dir: str,
    cases: list[dict[str, Any]],
    out_path: Path,
    temperature: float | None = None,
    p3_temperature: float | None = None,
) -> list[dict[str, Any]]:
    """Run 3-step chained prompts (P1 -> P2 -> P3) for v2, v3, or final."""
    pdir = ROOT / "prompts" / version_dir
    p1_sys, p1_usr = parse_prompt_markdown(pdir / "P1_question_generator.md")
    p2_sys, p2_usr = parse_prompt_markdown(pdir / "P2_answer_key_rubric.md")
    p3_sys, p3_usr = parse_prompt_markdown(pdir / "P3_quality_reviewer.md")

    results: list[dict[str, Any]] = []
    if out_path.exists():
        results = json.loads(out_path.read_text(encoding="utf-8"))
    done_ids = {r["case_id"] for r in results}

    for case in cases:
        if case["case_id"] in done_ids:
            continue
        print(f"[{version_dir}] Running {case['case_id']} ({case['note']})...", flush=True)

        p1_prompt = render_template(p1_usr, {**case, "constraints": case.get("constraints", "None")})
        p1_raw, m1 = generate_with_fallback(
            client, p1_prompt, system_instruction=p1_sys, temperature=temperature, json_mode=True
        )
        p1_json, p2_json, p3_json = None, None, None
        m2, m3 = None, None
        valid_json = False
        marks_match = False
        bloom_ok = False
        hinglish_clean = True

        try:
            p1_json = _extract_json_obj(p1_raw)
            if p1_json.get("status") == "REJECTED" or not p1_json.get("questions"):
                valid_json = True
                results.append(
                    {
                        "case_id": case["case_id"],
                        "note": case["note"],
                        "status": "REJECTED",
                        "models_used": {"p1": m1},
                        "valid_json": True,
                        "marks_match": True,
                        "bloom_ok": True,
                        "hinglish_clean": True,
                        "p1": p1_json,
                        "p2": None,
                        "p3": None,
                    }
                )
                out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"  -> REJECTED cleanly at P1 ({m1})", flush=True)
                continue

            q_json_str = json.dumps(p1_json["questions"], indent=2)
            p2_prompt = render_template(p2_usr, {**case, "questions_json": q_json_str})
            p2_raw, m2 = generate_with_fallback(
                client, p2_prompt, system_instruction=p2_sys, temperature=temperature, json_mode=True
            )
            p2_json = _extract_json_obj(p2_raw)

            pkg_str = json.dumps(
                {"questions": p1_json["questions"], "solutions": p2_json.get("solutions", [])}, indent=2
            )
            p3_prompt = render_template(p3_usr, {**case, "package_json": pkg_str})
            p3_raw, m3 = generate_with_fallback(
                client,
                p3_prompt,
                system_instruction=p3_sys,
                temperature=p3_temperature if p3_temperature is not None else temperature,
                json_mode=True,
            )
            p3_json = _extract_json_obj(p3_raw)
            valid_json = True

            sols = p2_json.get("solutions", [])
            marks_match = bool(sols) and all(
                abs(float(s.get("total_marks", -1)) - float(case["marks_per_question"])) < 1e-6
                and abs(sum(float(c.get("marks", 0)) for c in s.get("marking_scheme", [])) - float(case["marks_per_question"])) < 1e-6
                for s in sols
            )

            target_verbs = BLOOM_VERBS.get(case["bloom_level"], set())
            bloom_ok = all(
                (q.get("action_verb", "").lower() in target_verbs)
                or any(v in q.get("question_text", "").lower().split()[:8] for v in target_verbs)
                for q in p1_json["questions"]
            )

            all_text = " ".join(q.get("question_text", "").lower() for q in p1_json["questions"])
            tokens = set(re.findall(r"[a-zA-Z]+", all_text))
            hinglish_clean = not bool(tokens & HINGLISH_MARKERS)

        except Exception as exc:  # noqa: BLE001
            print(f"  -> JSON/Eval parse error: {exc}", flush=True)

        results.append(
            {
                "case_id": case["case_id"],
                "note": case["note"],
                "status": "OK" if valid_json else "PARSE_ERR",
                "models_used": {"p1": m1, "p2": m2, "p3": m3},
                "valid_json": valid_json,
                "marks_match": marks_match,
                "bloom_ok": bloom_ok,
                "hinglish_clean": hinglish_clean,
                "p1": p1_json if p1_json is not None else p1_raw,
                "p2": p2_json,
                "p3": p3_json,
            }
        )
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(
            f"  -> done ({m1}/{m2}/{m3}), json={valid_json}, marks={marks_match}, bloom={bloom_ok}",
            flush=True,
        )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v2", "v3", "final"], required=True)
    args = parser.parse_args()

    api_key = load_env_key()
    client = make_client(api_key)
    corpus = load_corpus()
    cases = benchmark_cases(corpus)

    temp = 0.2 if args.version == "final" else None
    p3_temp = 0.1 if args.version == "final" else None
    out_file = ROOT / "test-data" / f"{args.version}_eval.json"
    out = run_chained_version(client, args.version, cases, out_file, temperature=temp, p3_temperature=p3_temp)

    n = len(out)
    print(
        f"Summary [{args.version}]: json={sum(r['valid_json'] for r in out)}/{n}, "
        f"marks={sum(r['marks_match'] for r in out)}/{n}, "
        f"bloom={sum(r['bloom_ok'] for r in out)}/{n}, "
        f"hinglish_clean={sum(r['hinglish_clean'] for r in out)}/{n}"
    )
