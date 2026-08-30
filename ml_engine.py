"""Machine-learning helpers for IntelliHostel.

Models are intentionally lightweight so the project can run on a normal
college laptop. They are trained from data/training_data.csv on first use.
"""
from __future__ import annotations

import os
import re
import sqlite3
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(BASE_DIR, "data", "training_data.csv")


def _clean(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _models():
    df = pd.read_csv(DATASET).fillna("")
    text = (df["title"].astype(str) + " " + df["description"].astype(str)).map(_clean)

    category_model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=1200, class_weight="balanced")),
    ])
    category_model.fit(text, df["category"])

    priority_model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=1200, class_weight="balanced")),
    ])
    priority_model.fit(text, df["priority"])

    # A compact numeric/text regression model. The target is synthetic training
    # data representing expected days for a hostel maintenance team.
    regression_model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("reg", Ridge(alpha=1.0)),
    ])
    regression_model.fit(text + " " + df["priority"].map(_clean), df["resolution_days"].astype(float))

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    corpus_matrix = vectorizer.fit_transform(text)

    return category_model, priority_model, regression_model, vectorizer, corpus_matrix, df


def predict_complaint(title: str, description: str, selected_category: str = "", selected_priority: str = "") -> dict[str, Any]:
    """Predict category, priority and expected resolution time."""
    category_model, priority_model, regression_model, *_ = _models()
    text = _clean(f"{title} {description}")

    cat_probs = category_model.predict_proba([text])[0]
    cat_idx = int(np.argmax(cat_probs))
    category = category_model.classes_[cat_idx]
    category_conf = float(cat_probs[cat_idx])

    pri_probs = priority_model.predict_proba([text])[0]
    pri_idx = int(np.argmax(pri_probs))
    priority = priority_model.classes_[pri_idx]
    priority_conf = float(pri_probs[pri_idx])

    # User-selected values remain authoritative, while AI predictions are kept
    # separately for comparison/explanation.
    final_category = selected_category or category
    final_priority = selected_priority or priority
    reg_text = _clean(f"{title} {description} {final_priority}")
    days = float(np.clip(regression_model.predict([reg_text])[0], 0.5, 14.0))

    return {
        "predicted_category": category,
        "category_confidence": round(category_conf * 100, 1),
        "predicted_priority": priority,
        "priority_confidence": round(priority_conf * 100, 1),
        "resolution_days": round(days, 1),
        "final_category": final_category,
        "final_priority": final_priority,
    }


def find_duplicate(title: str, description: str, complaints: list[sqlite3.Row], threshold: float = 0.72) -> dict[str, Any] | None:
    """Find the most similar existing complaint using TF-IDF cosine similarity."""
    if not complaints:
        return None

    _, _, _, vectorizer, _, _ = _models()
    texts = [_clean(f"{row['title']} {row['description']}") for row in complaints]
    query = vectorizer.transform([_clean(f"{title} {description}")])

    # Refit a small vectorizer on current complaint text so new vocabulary is
    # represented. This is independent of the classifier training corpus.
    current_vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    matrix = current_vectorizer.fit_transform(texts + [_clean(f"{title} {description}")])
    scores = cosine_similarity(matrix[-1], matrix[:-1])[0]
    if len(scores) == 0:
        return None
    idx = int(np.argmax(scores))
    similarity = float(scores[idx])
    if similarity < threshold:
        return None

    row = complaints[idx]
    return {
        "id": row["id"],
        "similarity": round(similarity * 100, 1),
        "title": row["title"],
        "status": row["status"],
    }
