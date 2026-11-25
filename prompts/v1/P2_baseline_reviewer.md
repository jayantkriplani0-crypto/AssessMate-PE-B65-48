# Version v1 — Baseline Reviewer Prompt (Milestone 1)

- **Version:** `v1` (Baseline from Milestone 1 Q18)
- **Role:** Quality check reviewer prompt

## System Prompt
none

## User Prompt Template
Review the generated questions against the same syllabus. Check clarity, relevance, answerability, Bloom’s-level alignment, answer accuracy, and mark consistency. Flag issues and suggest corrections. Do not claim a question is correct unless supported by the syllabus. A teacher must approve final material.

Inputs:
- Syllabus Excerpt: {syllabus_excerpt}
- Generated Questions & Solutions: {generated_output}
