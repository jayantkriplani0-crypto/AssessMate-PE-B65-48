# AssessMate: Exam Question Generator with Quality Check

**Course:** Prompt Engineering (`SCSE4041`) — B.Tech 5th Semester, Bennett University  
**Problem Pool ID:** `C3` (Exam question generator with quality check)  
**Team ID:** `PE-B65-48` | **Team Name:** `BEYOND THE PROMPT` | **Batch:** `B65-80`  
**Faculty Mentor:** Sonal Kukreja  
**Main AI Tool & Model:** Gemini Flash-Lite (`gemini-flash-lite-latest` / `gemini-3.5-flash-lite` via `google-genai` SDK) + Streamlit + TF-IDF RAG

---

## What AssessMate Does
AssessMate converts a **syllabus source** (uploaded PDF/TXT, custom excerpt, or indexed public CS syllabus corpus), **topic**, **learning outcome**, **Revised Bloom's taxonomy level**, **question type** (`Short Answer`, `Long Answer`, `MCQ`, `Numerical`), **difficulty**, **quantity**, and **marks** through a 4-module pipeline:

1. **Syllabus Grounding (RAG) and Input Validator (`code/rag.py`):** Validates constraints and retrieves top-2 grounded syllabus passages using TF-IDF scoring.
2. **Bloom-Aligned Exam Question Generator (`P1`):** Generates syllabus-bounded questions anchored to target Bloom's action verbs (or returns `REJECTED` if off-syllabus).
3. **Answer Key and Marking Scheme Generator (`P2`):** Produces syllabus-grounded model answers and observable stepwise rubrics verified in Python to sum strictly to target marks.
4. **Quality Check Reviewer and Revision Engine (`P3`):** Audits every question-solution pair on a 1–5 scale across 5 rubric axes (`Clarity`, `Syllabus Relevance`, `Answerability`, `Bloom Alignment`, `Difficulty`), flags `REVISE` with a concrete rewrite when needed, and attaches a faculty verification note.

---

## Live Prototype & Links
- **Deployed Streamlit Prototype:** `https://assessmate-pe-b65-48-ievwpkiytzlhkjngeyagn9.streamlit.app/`
- **GitHub Repository:** `https://github.com/jayantkriplani0-crypto/AssessMate-PE-B65-48`

---

## Team Members
| Enrollment No. | Name | Role / Main Task |
| :--- | :--- | :--- |
| `S24CSEU2763` | Jayant Kriplani (Team Leader) | `[To be filled before submission]` |
| `S24CSEU2764` | Shubham Mittal | `[To be filled before submission]` |
| `S24CSEU2827` | Ajay Chopra | `[To be filled before submission]` |

---

## Repository Structure
```text
├── README.md
├── CHANGELOG.md
├── .gitignore
├── prompts/
│   ├── v1/                  # Milestone 1 baseline generation & reviewer prompts
│   ├── v2/                  # Decomposed P1/P2/P3 JSON pipeline
│   ├── v3/                  # Added Bloom verbs, MCQ rules, few-shot JSON & 5-axis rubric
│   └── final/               # Production v4 P1, P2, P3 prompt templates
├── code/
│   ├── rag.py               # Module 1: PDF/corpus chunking, TF-IDF retrieval & validator
│   ├── pipeline.py          # Modules 2–4: 3-prompt chaining & Gemini fallback engine
│   ├── app.py               # Streamlit web prototype
│   ├── eval_versions.py     # Version benchmark runner (v1–v3)
│   ├── run_tests.py         # 12-case evaluation suite (7 Normal, 3 Edge, 2 Invalid)
│   └── requirements.txt
├── test-data/
│   ├── cs_syllabus_corpus.json
│   ├── test_inputs.json
│   ├── test_results.json
│   ├── test_results.md
│   └── v1/v2/v3 eval logs
├── docs/
│   ├── diagrams/            # 5 original SVG diagrams (Workflow, Decomposition, I/O, Arch, RAG)
│   ├── screenshots/         # Live Streamlit run & repository screenshots
│   ├── REEL_SCRIPT.md       # 120-second demo script
│   ├── build_pdfs.py        # Reproducible HTML-to-PDF generator
│   ├── BEYOND_THE_PROMPT_TechnicalReport.pdf
│   └── M2_PE-B65-48_AssessMate.pdf
└── submission/              # Exact upload-ready PDFs for Form Q16 & Q21
```

---

## How to Open & Run Locally
1. Install dependencies:
   ```bash
   pip install -r code/requirements.txt
   ```
2. Provide your Gemini API key via environment variable (never commit `.env` or keys):
   ```powershell
   $env:GEMINI_API_KEY="your-api-key-here"
   ```
3. Launch the Streamlit app:
   ```bash
   streamlit run code/app.py
   ```
4. Run the 12-case evaluation suite:
   ```bash
   python code/run_tests.py
   ```
