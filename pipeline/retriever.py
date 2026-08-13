"""
pipeline/retriever.py — Two-stage RAG retrieval.

Stage 1: cosine similarity, top K=4, threshold 0.75.
Stage 2: structured LLM call → SUPPORTED / PARTIAL / UNSUPPORTED.
Placeholder guard: if the top chunk is flagged, force UNSUPPORTED.
"""

from __future__ import annotations
from typing import Optional
import json
import re
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import (
    LLM_MODEL, EMBEDDING_MODEL,
    SIMILARITY_THRESHOLD, TOP_K,
    EVIDENCE_SUPPORTED, EVIDENCE_PARTIAL, EVIDENCE_UNSUPPORTED,
)
from pipeline.indexer import Chunk

_client = None


def _get_client():
    global _client
    if _client is None:
        import os
        from openai import OpenAI
        _client = OpenAI(api_key=os.getenv("LLM_API_KEY"))
    return _client


# --------------------------------------------------------------------------
# In-memory vector index
# --------------------------------------------------------------------------

_chunks: list[Chunk] = []
_embeddings: Optional[np.ndarray] = None  # shape (N, D)


def _embed_text(text: str) -> list[float]:
    response = _get_client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=text[:8000],  # safety trim
    )
    return response.data[0].embedding


def build_index(chunks: list[Chunk]) -> None:
    """Embed all chunks and store in memory. Call at startup and after upload."""
    global _chunks, _embeddings
    if not chunks:
        _chunks = []
        _embeddings = None
        return

    print(f"[retriever] Embedding {len(chunks)} chunks …")
    vectors = []
    for i, chunk in enumerate(chunks):
        vec = _embed_text(chunk.text)
        chunk.embedding = vec
        vectors.append(vec)
        if (i + 1) % 10 == 0:
            print(f"[retriever]   {i+1}/{len(chunks)}")

    _chunks = chunks
    _embeddings = np.array(vectors, dtype=np.float32)
    # L2-normalise for cosine similarity via dot product
    norms = np.linalg.norm(_embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    _embeddings /= norms
    print(f"[retriever] Index ready with {len(_chunks)} chunks.")


def add_chunks(new_chunks: list[Chunk]) -> None:
    """Append new chunks to the existing index (after upload)."""
    global _chunks, _embeddings
    if not new_chunks:
        return
    for chunk in new_chunks:
        chunk.embedding = _embed_text(chunk.text)
    new_vecs = np.array([c.embedding for c in new_chunks], dtype=np.float32)
    norms = np.linalg.norm(new_vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    new_vecs /= norms

    _chunks.extend(new_chunks)
    if _embeddings is None:
        _embeddings = new_vecs
    else:
        _embeddings = np.vstack([_embeddings, new_vecs])


# --------------------------------------------------------------------------
# Stage 1 — cosine retrieval
# --------------------------------------------------------------------------

def retrieve(query: str, k: int = TOP_K) -> tuple[list[Chunk], list[float]]:
    """
    Returns (top_chunks, scores). Both lists may be empty if no chunk
    passes the similarity threshold or if the index is empty.
    """
    if _embeddings is None or len(_chunks) == 0:
        return [], []

    q_vec = np.array(_embed_text(query), dtype=np.float32)
    q_norm = np.linalg.norm(q_vec)
    if q_norm == 0:
        return [], []
    q_vec /= q_norm

    scores = _embeddings @ q_vec  # cosine similarities
    top_idx = np.argsort(scores)[::-1][:k]
    top_scores = scores[top_idx].tolist()
    top_chunks = [_chunks[i] for i in top_idx]

    # Filter by threshold
    passing = [(c, s) for c, s in zip(top_chunks, top_scores) if s >= SIMILARITY_THRESHOLD]
    if not passing:
        return [], []

    chunks_out, scores_out = zip(*passing)
    return list(chunks_out), list(scores_out)


# --------------------------------------------------------------------------
# Placeholder guard
# --------------------------------------------------------------------------

def check_placeholder_block(chunks: list[Chunk]) -> bool:
    """Return True if the top chunk is placeholder-flagged."""
    return bool(chunks) and chunks[0].placeholder_flagged


# --------------------------------------------------------------------------
# Stage 2 — evidence check (structured LLM call)
# --------------------------------------------------------------------------

_EVIDENCE_SYSTEM = """You are an evidence grader for a RAG support system.
Given a customer question and retrieved knowledge base passages, return exactly:
{"verdict": "SUPPORTED"} if the passages fully answer the question,
{"verdict": "PARTIAL"}    if they partially cover it and one clarifying question would help,
{"verdict": "UNSUPPORTED"} if the passages do not support an answer.
Return ONLY the JSON object, nothing else."""


def evidence_check(query: str, chunks: list[Chunk]) -> str:
    """Stage 2: returns SUPPORTED, PARTIAL, or UNSUPPORTED."""
    if not chunks:
        return EVIDENCE_UNSUPPORTED

    context = "\n\n---\n\n".join(c.text for c in chunks)
    user_msg = f"Question: {query}\n\nPassages:\n{context}"

    try:
        resp = _get_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _EVIDENCE_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_completion_tokens=20,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        data = json.loads(raw)
        verdict = data.get("verdict", EVIDENCE_UNSUPPORTED).upper()
        if verdict not in (EVIDENCE_SUPPORTED, EVIDENCE_PARTIAL, EVIDENCE_UNSUPPORTED):
            return EVIDENCE_UNSUPPORTED
        return verdict
    except Exception:
        return EVIDENCE_UNSUPPORTED


# --------------------------------------------------------------------------
# Combined retrieval pipeline
# --------------------------------------------------------------------------

def retrieve_and_grade(query: str) -> dict:
    """
    Returns a dict with:
      chunks, scores, top_score, verdict, placeholder_blocked, subsections
    """
    chunks, scores = retrieve(query)
    top_score = scores[0] if scores else 0.0

    # Placeholder guard
    placeholder_blocked = False
    if check_placeholder_block(chunks):
        placeholder_blocked = True
        verdict = EVIDENCE_UNSUPPORTED
    elif not chunks:
        verdict = EVIDENCE_UNSUPPORTED
    else:
        verdict = evidence_check(query, chunks)

    subsections = ",".join(c.subsection for c in chunks if c.subsection)

    return {
        "chunks": chunks,
        "scores": scores,
        "top_score": top_score,
        "verdict": verdict,
        "placeholder_blocked": placeholder_blocked,
        "subsections": subsections,
    }
