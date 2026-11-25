# AssessMate 120-Second Milestone 2 Reel Script (Q13 & Q14)

- **Target Duration:** **120 seconds** (must stay strictly between **90 and 150 seconds**)
- **Where to Upload:** YouTube (Unlisted) or Google Drive
- **Access Setting:** **"Anyone with the link can view"** *(test in an Incognito browser window!)*
- **Format:** Real screen recording of your live Streamlit app + voice-over (and optional captions). **Do not use static slide mock-ups.**

---

## Segment-by-Segment Script

### 1. Problem (~15 seconds | 0:00 – 0:15)
* **On Screen:** Show the GitHub README or the top header of your live **AssessMate** Streamlit app.
* **Voice-Over:**
  > "Hi, we are Team BEYOND THE PROMPT, Team ID PE-B65-48, presenting AssessMate for Problem C3. Faculty spend hours writing syllabus-aligned exam questions, model answers, and balanced marking schemes. Single prompts frequently drift off-syllabus or break Bloom's taxonomy alignment—so we built a retrieval-grounded 3-prompt solution."

---

### 2. Prompt Experiment — Before & After (~35 seconds | 0:15 – 0:50)
* **On Screen:** Open `prompts/v1/P1_baseline_generation.md` and `test-data/v1_baseline_eval.json` (showing unstructured Markdown and Bloom drift), then switch to `prompts/final/P1_question_generator.md` and `P3_quality_reviewer.md`.
* **Voice-Over:**
  > "In Milestone 1, our baseline v1 prompt bundled questions, answers, and rubrics into one zero-shot call—producing 0 out of 6 machine-readable JSON outputs and drifting on Bloom's levels. Across v2, v3, and v4, we decomposed the pipeline into P1 Generator, P2 Answer Key and Exact-Sum Rubric, and P3 Quality Reviewer, adding TF-IDF syllabus retrieval, Bloom's action verbs, few-shot JSON exemplars, and a 5-axis 1-to-5 moderation rubric."

---

### 3. Live Working Demo (~50 seconds | 0:50 – 1:40)
* **On Screen:** On the **live deployed Streamlit app**:
  1. Select **"Normal: BST Deletion & Inorder (Apply)"** → Click **Run 3-Step Prompt Pipeline** → Click through **Questions (P1)**, **Answer Keys & Rubrics (P2)** (showing exact `5.0 / 5` mark sum), **Quality Review (P3)** (showing 5-axis scores and `PASS`), and **RAG Context & Prompts** (showing retrieved `CS-DSA-01` chunk).
  2. Select **"Edge: Broad Syllabus for 2 Marks"** → Run → Open **Quality Review (P3)** showing the reviewer catching the scope-vs-marks mismatch (`REVISE`) and generating a focused rewritten question.
  3. Select **"Invalid: Vague Topic ('idk')"** → Run → Show Module 1 rejecting it cleanly before calling Gemini.
* **Voice-Over:**
  > "Here is AssessMate running live. For Binary Search Trees at Apply level, Module 1 retrieves the matching syllabus passage, P1 generates structured questions, P2 produces rubrics summing strictly to 5 marks, and P3 audits all five quality axes. On an over-scoped 2-mark request, P3 flags REVISE with an improved question, and vague inputs like 'idk' are blocked cleanly at validation."

---

### 4. Progress & Next Steps (~20 seconds | 1:40 – 2:00)
* **On Screen:** Show `test-data/test_results.md` (12 Normal/Edge/Invalid tests) and your public GitHub repository (`AssessMate-PE-B65-48`).
* **Voice-Over:**
  > "All four modules are working and verified across 12 test cases, with versioned prompts and our Technical Report pushed to GitHub. For Milestone 3, we will add dense semantic embeddings for PDF retrieval, multi-pass reviewer consistency voting, and printable PDF exam paper export. Thank you!"
