"""Module 1: Syllabus Grounding (Lightweight RAG Retriever) & Input Validator."""

from __future__ import annotations

import io
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]

BLOOM_LEVELS: dict[str, list[str]] = {
    "Remember": ["define", "list", "recall", "state", "identify", "name"],
    "Understand": ["explain", "summarize", "classify", "compare", "interpret", "describe"],
    "Apply": ["compute", "trace", "implement", "solve", "demonstrate", "apply", "calculate"],
    "Analyze": ["differentiate", "examine", "diagnose", "decompose", "contrast", "analyze"],
    "Evaluate": ["critique", "justify", "assess", "recommend", "prioritize", "evaluate"],
    "Create": ["design", "formulate", "construct", "synthesize", "propose", "architect"],
}

QUESTION_TYPES = ["Short Answer", "Long Answer", "MCQ", "Numerical"]
DIFFICULTIES = ["Easy", "Medium", "Hard"]
INVALID_TOPICS = {"idk", "test", "na", "n/a", "none", "asdf", "qwerty", "abc", "xyz"}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
    "be", "by", "as", "at", "from", "that", "this", "it", "which", "using", "into",
}


@dataclass
class AssessmentRequest:
    topic: str
    bloom_level: str
    question_type: str = "Short Answer"
    difficulty: str = "Medium"
    num_questions: int = 2
    marks_per_question: int = 5
    learning_outcome: str = ""
    constraints: str = "None"
    syllabus_text: str = ""


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


def load_default_syllabus_chunks() -> list[dict[str, str]]:
    """Load the standard public CS syllabus corpus chunks."""
    corpus_path = ROOT / "test-data" / "cs_syllabus_corpus.json"
    return json.loads(corpus_path.read_text(encoding="utf-8"))


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract clean text from an uploaded syllabus PDF."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)


def chunk_syllabus_text(raw_text: str, max_words: int = 160) -> list[dict[str, str]]:
    """Split user-supplied syllabus text into retrievable chunks."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", raw_text) if p.strip()]
    chunks: list[dict[str, str]] = []
    idx = 1
    for para in paragraphs:
        words = para.split()
        if len(words) <= max_words:
            chunks.append(
                {
                    "chunk_id": f"USR-{idx:02d}",
                    "subject": "Uploaded Syllabus",
                    "topic": "User Provided Context",
                    "learning_outcome": "",
                    "text": para,
                }
            )
            idx += 1
        else:
            step = max(80, max_words - 25)
            for start in range(0, len(words), step):
                part = " ".join(words[start : start + max_words])
                chunks.append(
                    {
                        "chunk_id": f"USR-{idx:02d}",
                        "subject": "Uploaded Syllabus",
                        "topic": "User Provided Context",
                        "learning_outcome": "",
                        "text": part,
                    }
                )
                idx += 1
    return chunks


def retrieve_relevant_chunks(
    query: str,
    chunks: list[dict[str, str]],
    top_k: int = 2,
) -> list[dict[str, Any]]:
    """Score and retrieve top-k syllabus passages via BM25-style TF-IDF cosine + keyword overlap."""
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return [{**c, "score": 0.0} for c in chunks[:top_k]]

    docs_tokens = [_tokenize(f"{c.get('topic', '')} {c.get('subject', '')} {c['text']}") for c in chunks]
    num_docs = len(docs_tokens)
    df: dict[str, int] = {}
    for dtoks in docs_tokens:
        for tok in set(dtoks):
            df[tok] = df.get(tok, 0) + 1

    scored: list[dict[str, Any]] = []
    q_set = set(query_tokens)
    for chunk, dtoks in zip(chunks, docs_tokens):
        if not dtoks:
            scored.append({**chunk, "score": 0.0})
            continue
        tf_counts: dict[str, int] = {}
        for tok in dtoks:
            tf_counts[tok] = tf_counts.get(tok, 0) + 1

        score = 0.0
        for q in q_set:
            if q in tf_counts:
                idf = math.log(1.0 + (num_docs + 0.5) / (df.get(q, 0) + 0.5))
                tf = tf_counts[q] / (len(dtoks) + 5.0)
                score += tf * idf * 10.0

        # Boost exact topic substring matches
        topic_str = chunk.get("topic", "").lower()
        if any(q in topic_str for q in q_set if len(q) >= 3):
            score += 0.5

        scored.append({**chunk, "score": round(score, 3)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def validate_request(req: AssessmentRequest) -> tuple[bool, list[str]]:
    """Validate all user parameters before calling Gemini."""
    errors: list[str] = []
    topic = (req.topic or "").strip()
    alpha_count = sum(c.isalpha() for c in topic)

    if not topic:
        errors.append("Syllabus topic cannot be empty.")
    elif len(topic) < 4 or alpha_count < 4 or topic.lower() in INVALID_TOPICS:
        errors.append(f"Topic '{topic}' is too vague or meaningless for exam question generation.")

    if req.bloom_level not in BLOOM_LEVELS:
        errors.append(
            f"Invalid Bloom's level '{req.bloom_level}'. Must be one of: {', '.join(BLOOM_LEVELS)}."
        )

    if req.question_type not in QUESTION_TYPES:
        errors.append(
            f"Invalid question type '{req.question_type}'. Must be one of: {', '.join(QUESTION_TYPES)}."
        )

    if req.difficulty not in DIFFICULTIES:
        errors.append(f"Invalid difficulty '{req.difficulty}'. Must be Easy, Medium, or Hard.")

    if not isinstance(req.num_questions, int) or req.num_questions < 1 or req.num_questions > 10:
        errors.append(f"Quantity ({req.num_questions}) must be an integer between 1 and 10.")

    if not isinstance(req.marks_per_question, int) or req.marks_per_question < 1 or req.marks_per_question > 20:
        errors.append(f"Marks per question ({req.marks_per_question}) must be an integer between 1 and 20.")

    low_c = (req.constraints or "").lower()
    if ("numerical" in low_c or "calculation" in low_c) and (
        "no math" in low_c or "zero math" in low_c or "no numerical" in low_c or "no formula" in low_c
    ):
        errors.append("Contradictory constraints detected: numerical calculation requested alongside no math/formulas.")

    if req.question_type == "Numerical" and ("no math" in low_c or "zero math" in low_c or "no numerical" in low_c):
        errors.append("Contradictory parameters: Numerical question type selected with no-math constraint.")

    return len(errors) == 0, errors


def build_grounded_context(req: AssessmentRequest, top_k: int = 2) -> dict[str, Any]:
    """Retrieve syllabus chunks for the request and return context + metadata."""
    raw = (req.syllabus_text or "").strip()
    if raw:
        chunks = chunk_syllabus_text(raw)
        source_mode = "custom_syllabus"
    else:
        chunks = load_default_syllabus_chunks()
        source_mode = "public_cs_corpus"

    query = f"{req.topic} {req.learning_outcome}".strip()
    retrieved = retrieve_relevant_chunks(query, chunks, top_k=top_k)
    excerpt = "\n\n".join(f"[{c['chunk_id']} | {c['subject']}] {c['text']}" for c in retrieved)
    top_score = retrieved[0]["score"] if retrieved else 0.0

    return {
        "source_mode": source_mode,
        "total_chunks_indexed": len(chunks),
        "retrieved_chunks": retrieved,
        "top_retrieval_score": top_score,
        "syllabus_excerpt": excerpt,
        "request": asdict(req),
    }
