from __future__ import annotations

from collections import Counter
from math import sqrt
import re
from typing import Dict, List, Sequence

import numpy as np


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _bow_cosine_scores(candidates: Sequence[str], corpus: Sequence[str]) -> np.ndarray:
    corpus_counters = [Counter(_tokenize(text)) for text in corpus]
    cand_counters = [Counter(_tokenize(text)) for text in candidates]

    if not corpus_counters or not cand_counters:
        return np.zeros((len(candidates), len(corpus)), dtype=float)

    corpus_norms = [sqrt(sum(v * v for v in counter.values())) or 1.0 for counter in corpus_counters]
    cand_norms = [sqrt(sum(v * v for v in counter.values())) or 1.0 for counter in cand_counters]

    scores = np.zeros((len(candidates), len(corpus)), dtype=float)
    for i, cand_counter in enumerate(cand_counters):
        if not cand_counter:
            continue
        for j, corpus_counter in enumerate(corpus_counters):
            if not corpus_counter:
                continue
            common = set(cand_counter) & set(corpus_counter)
            if not common:
                continue
            dot = sum(cand_counter[token] * corpus_counter[token] for token in common)
            scores[i, j] = dot / (cand_norms[i] * corpus_norms[j])
    return scores


def _encode_texts(model_name: str, texts: Sequence[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, device="cpu")
    embeddings = model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
    return embeddings


def _similarity_scores(model_name: str, candidate_texts: Sequence[str], corpus_texts: Sequence[str]) -> np.ndarray:
    try:
        corpus_emb = _encode_texts(model_name, corpus_texts)
        cand_emb = _encode_texts(model_name, candidate_texts)
        return cand_emb @ corpus_emb.T  # cosine because normalized
    except Exception as exc:
        print(f"Embedding rerank unavailable ({exc}); falling back to bag-of-words cosine.")
        return _bow_cosine_scores(candidate_texts, corpus_texts)


def rerank_by_embedding(
    candidates: List[Dict],
    corpus: List[Dict],
    model_name: str,
    top_k: int,
    max_corpus: int = None,
) -> List[Dict]:
    """
    Rerank candidate papers by similarity to the Zotero corpus.

    Preferred path:
    - sentence-transformers embeddings on CPU

    Fallback path:
    - bag-of-words cosine similarity when the local transformer stack is broken
    """
    if max_corpus:
        corpus = corpus[:max_corpus]
    if not corpus or not candidates:
        return []

    corpus_texts = [paper.get("abstract", "") for paper in corpus]
    candidate_texts = [paper.get("abstract", "") for paper in candidates]
    scores = _similarity_scores(model_name, candidate_texts, corpus_texts)
    avg_scores = scores.mean(axis=1) if scores.size else np.zeros(len(candidates), dtype=float)

    ranked: List[Dict] = []
    for paper, score in zip(candidates, avg_scores):
        ranked.append({**paper, "score": float(score)})

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_k]
