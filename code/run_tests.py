"""Execute the 12-case AssessMate test suite against the final pipeline."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from pipeline import AssessmentRequest, load_api_key, run_assessmate_pipeline  # noqa: E402
from rag import BLOOM_LEVELS  # noqa: E402

HINGLISH_MARKERS = {"samjhao", "banao", "kya", "kaise", "aur", "liye", "pe", "bhai", "karo", "hai"}


def evaluate_result(case: dict[str, Any], res: dict[str, Any]) -> tuple[str, str]:
    """Evaluate actual pipeline output honestly against expected behavior."""
    tno = case["test_no"]
    status = res.get("status")

    if case["type"] == "Invalid" or tno == 9:
        if status == "REJECTED":
            errs = "; ".join(res.get("validation_errors", []))
            return "Pass", f"REJECTED at {res.get('rejected_stage')}: {errs[:85]}"
        return "Fail", "Accepted invalid or out-of-syllabus request instead of rejecting."

    if tno == 13:
        chunk_ids = [c.get("chunk_id") for c in res.get("rag_context", {}).get("retrieved_chunks", [])]
        if "CS-DSA-02" in chunk_ids and status == "OK":
            return "Pass", f"Retrieved {chunk_ids} and generated Master Theorem Q"
        return (
            "Fail",
            f"Lexical TF-IDF retrieved {chunk_ids} (missed CS-DSA-02); status={status}",
        )

    if status != "OK":
        return "Fail", f"Unexpected rejection: {res.get('validation_errors')}"

    questions = res["p1_output"].get("questions", [])
    solutions = res["p2_output"].get("solutions", [])
    reviews = res["p3_output"].get("reviews", [])
    summary = res["p3_output"].get("summary", {})
    marks_ok = bool(solutions) and all(s.get("marks_sum_valid") for s in solutions)

    if tno == 8:
        q_text = " ".join(q.get("question_text", "").lower() for q in questions)
        tokens = set(re.findall(r"[a-zA-Z]+", q_text))
        has_hinglish = bool(tokens & HINGLISH_MARKERS)
        covers_both = ("congestion" in q_text or "cwnd" in q_text or "slow start" in q_text) and (
            "handshake" in q_text or "syn" in q_text
        )
        verdict = reviews[0].get("verdict", "?") if reviews else "?"
        if has_hinglish:
            return "Fail", f"Hinglish tokens leaked; P3 verdict {verdict}"
        if not covers_both:
            return "Fail", f"Formal English ok, but omitted one requested sub-topic; P3 {verdict}"
        return "Pass", f"Formal English + both sub-topics covered; P3 {verdict}"

    if tno == 10:
        if any(r.get("verdict") == "REVISE" for r in reviews):
            sc = reviews[0].get("scores", {})
            return (
                "Pass",
                f"P3 flagged REVISE (ans={sc.get('answerability')}/5, diff={sc.get('difficulty')}/5) + rewrite",
            )
        return "Fail", "P3 missed broad-scope vs 2-mark mismatch (returned PASS)."

    # Normal cases 1-7
    target_verbs = {v.lower() for v in BLOOM_LEVELS.get(case["bloom_level"], [])}
    verb_ok = all(
        (q.get("action_verb", "").lower() in target_verbs)
        or any(v in q.get("question_text", "").lower().split()[:8] for v in target_verbs)
        for q in questions
    )
    passed_cnt = summary.get("passed", 0)
    avg_sc = summary.get("average_quality_score", "-")
    if len(questions) == case["num_questions"] and marks_ok and passed_cnt == len(questions) and verb_ok:
        return (
            "Pass",
            f"{len(questions)} {case['question_type']} ({case['bloom_level']}) Qs, {case['marks_per_question']}M rubric ok, P3 PASS ({avg_sc}/5)",
        )
    return (
        "Fail",
        f"Qs={len(questions)}/{case['num_questions']}, marks_ok={marks_ok}, verb_ok={verb_ok}, P3_pass={passed_cnt}/{len(questions)}",
    )


def main() -> None:
    inputs_path = ROOT / "test-data" / "test_inputs.json"
    results_json_path = ROOT / "test-data" / "test_results.json"
    results_md_path = ROOT / "test-data" / "test_results.md"

    cases = json.loads(inputs_path.read_text(encoding="utf-8"))
    api_key = load_api_key()

    existing: dict[int, dict[str, Any]] = {}
    if results_json_path.exists():
        for item in json.loads(results_json_path.read_text(encoding="utf-8")):
            existing[item["test_no"]] = item

    records: list[dict[str, Any]] = []
    for case in cases:
        tno = case["test_no"]
        if tno in existing:
            records.append(existing[tno])
            continue
        print(f"Running Test {tno} ({case['type']}): {case['topic'][:45]}...", flush=True)
        req = AssessmentRequest(
            topic=case["topic"],
            bloom_level=case["bloom_level"],
            question_type=case["question_type"],
            difficulty=case["difficulty"],
            num_questions=case["num_questions"],
            marks_per_question=case["marks_per_question"],
            learning_outcome=case["learning_outcome"],
            constraints=case["constraints"],
        )
        res = run_assessmate_pipeline(req, api_key=api_key)
        verdict, actual_short = evaluate_result(case, res)

        t_short = case["topic"][:38] + ("..." if len(case["topic"]) > 38 else "")
        input_short = f"{t_short} ({case['bloom_level']}, {case['question_type']}, {case['num_questions']}x{case['marks_per_question']}M)"
        rec = {
            "test_no": tno,
            "input_short": input_short,
            "type": case["type"],
            "expected_output": case["expected_output"],
            "actual_output_short": actual_short,
            "pass_fail": verdict,
            "full_response": res,
        }
        records.append(rec)
        results_json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  -> {verdict}: {actual_short}", flush=True)

    md_lines = [
        "# AssessMate 12-Case Evaluation Results",
        "",
        "| Test No. | Input (Short) | Type | Expected Output | Actual Output (Short) | Pass / Fail |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for r in records:
        md_lines.append(
            f"| {r['test_no']} | {r['input_short']} | {r['type']} | {r['expected_output']} | {r['actual_output_short']} | {r['pass_fail']} |"
        )
    results_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    p_count = sum(1 for r in records if r["pass_fail"] == "Pass")
    print(f"Completed {len(records)} tests: {p_count} Pass, {len(records) - p_count} Fail.")


if __name__ == "__main__":
    main()
