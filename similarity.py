from typing import Dict, List, Sequence

import numpy as np
from sentence_transformers import SentenceTransformer


def _encode_texts(model_name: str, texts: Sequence[str]) -> np.ndarray:
    model = SentenceTransformer(model_name)
    embeddings = model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
    return embeddings


def rerank_by_embedding(
    candidates: List[Dict],
    corpus: List[Dict],
    model_name: str,
    top_k: int,
    max_corpus: int = None,
) -> List[Dict]:
    """
    Rerank candidate papers by cosine similarity to Zotero corpus abstracts.
    """
    if max_corpus:
        corpus = corpus[:max_corpus]
    if not corpus or not candidates:
        return []

    corpus_emb = _encode_texts(model_name, [p["abstract"] for p in corpus])
    cand_emb = _encode_texts(model_name, [p["abstract"] for p in candidates])

    scores = cand_emb @ corpus_emb.T  # cosine because normalized
    avg_scores = scores.mean(axis=1)

    ranked: List[Dict] = []
    for paper, score in zip(candidates, avg_scores):
        merged = {**paper, "score": float(score)}
        ranked.append(merged)

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]
