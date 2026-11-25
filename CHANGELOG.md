# Changelog — AssessMate (`PE-B65-48`)

Dated record of progress from Milestone 1 through Milestone 2.

## [2026-11-25] — Milestone 2 Final Build & Verification (`v4` / `final`)
- Finalized `prompts/final/` (`v4`) with formal academic English enforcement, sub-topic completeness checks, low-temperature tuning (`0.2` for P1/P2, `0.1` for P3), and out-of-syllabus refusal rules.
- Implemented `code/rag.py` (Module 1: TF-IDF syllabus chunk retrieval for PDFs/text/public CS corpus + input constraint validator).
- Implemented `code/pipeline.py` (Modules 2–4: 3-step chaining engine with deterministic mark-sum checks and Gemini Flash-Lite multi-model fallback).
- Built Streamlit interactive web application (`code/app.py`) with 5 output tabs, presets, PDF upload, and JSON/Markdown export.
- Executed full 12-case evaluation suite (`code/run_tests.py`) covering 7 Normal, 3 Edge, and 2 Invalid tests (`test-data/test_results.json`, `test-data/test_results.md`).
- Generated five original SVG architecture/workflow/RAG diagrams (`docs/diagrams/`), captured live UI and repo screenshots (`docs/screenshots/`), wrote the Reel script (`docs/REEL_SCRIPT.md`), and built `BEYOND_THE_PROMPT_TechnicalReport.pdf` and `M2_PE-B65-48_AssessMate.pdf`.

## [2026-11-25] — Prompt Iteration `v3` (Bloom's Verbs, Few-Shot JSON & 5-Axis Rubric)
- Added Revised Bloom's Cognitive Action Verb guide, 4-option MCQ formatting rules, and few-shot JSON exemplars in `P1` and `P2`.
- Upgraded `P3` with a 5-axis 1–5 scoring rubric (Clarity, Syllabus Relevance, Answerability, Bloom's Alignment, Difficulty) and forced `REVISE` rewrites.
- Benchmarked `v3` on `B1`–`B6` (`test-data/v3_eval.json`): improved to 6/6 valid JSON, 6/6 mark-sum match, and 6/6 Bloom verb alignment.

## [2026-11-25] — Prompt Iteration `v2` (Task Decomposition & JSON Schemas)
- Decomposed Milestone 1 single generation prompt into `P1` (Question Generator) and `P2` (Answer Key & Marking Scheme), paired with `P3` (Quality Reviewer).
- Added strict JSON schemas and `P1` out-of-syllabus refusal status; benchmarked `v2` on `B1`–`B6` (`test-data/v2_eval.json`: 4/6 JSON, 4/6 mark-sum, 3/6 Bloom alignment).

## [2026-10-09] — Milestone 1 Baseline (`v1`)
- Selected Problem `C3` (Exam Question Generator with Quality Check) from Appendix A.
- Defined inputs (syllabus excerpt, topic, learning outcomes, question type, Bloom's level, difficulty, quantity, marks) and outputs (questions, answer keys, marking schemes, quality review).
- Established initial `v1` baseline prompts (`prompts/v1/P1_baseline_generation.md` and `prompts/v1/P2_baseline_reviewer.md`) and benchmarked `v1` on `B1`–`B6` (`test-data/v1_baseline_eval.json`: 0/6 machine-readable JSON).
