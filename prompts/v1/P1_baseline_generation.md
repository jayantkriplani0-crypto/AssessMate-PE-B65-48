# Version v1 — Baseline Generation Prompt (Milestone 1)

- **Version:** `v1` (Baseline from Milestone 1 Q18)
- **Role:** Generation prompt (single-step questions + marks + answer key + marking scheme)

## System Prompt
none

## User Prompt Template
Use only the supplied syllabus excerpt. Generate the requested number and type of exam questions at the specified Bloom’s level and difficulty. For each, provide marks, an answer key, and a marking scheme. Do not add facts absent from the source.

Input Parameters:
- Syllabus Excerpt: {syllabus_excerpt}
- Topic: {topic}
- Bloom's Level: {bloom_level}
- Difficulty: {difficulty}
- Question Type: {question_type}
- Quantity: {num_questions}
- Marks: {marks_per_question}
