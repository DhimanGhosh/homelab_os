from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass
class CategoryPrediction:
    category: str
    confidence: float
    source: str
    alternatives: list[dict]


RULES = {
    "Grocery": ["grocery", "supermarket", "vegetables", "milk", "blinkit", "zepto", "swiggy instamart"],
    "Restaurant": ["restaurant", "cafe", "coffee", "zomato", "swiggy", "food", "pizza", "burger"],
    "Office Travel": ["uber", "ola", "cab", "auto", "metro", "office"],
    "Subscription": ["netflix", "spotify", "amazon prime", "hotstar", "youtube", "subscription"],
    "Medicine": ["pharmacy", "chemist", "medicine", "doctor", "hospital", "clinic"],
    "Online Shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho"],
    "Mobile Recharge": ["recharge", "airtel", "jio", "vi", "bsnl"],
    "Utilities": ["electricity", "water", "gas", "bill", "broadband", "wifi"],
    "Flat/Rent": ["rent", "flat", "maintenance", "society"],
    "Movies": ["movie", "cinema", "pvr", "inox", "bookmyshow"],
    "ATM Cash": ["atm", "cash withdrawal"],
}


def rule_prediction(description: str) -> CategoryPrediction:
    desc = (description or "").lower()
    matches = []
    for category, keywords in RULES.items():
        hit_count = sum(1 for kw in keywords if kw in desc)
        if hit_count:
            matches.append((category, min(0.95, 0.55 + hit_count * 0.15)))
    if not matches:
        return CategoryPrediction("Other", 0.0, "rules", [])
    matches.sort(key=lambda item: item[1], reverse=True)
    alternatives = [{"category": cat, "confidence": round(conf, 3)} for cat, conf in matches[:3]]
    return CategoryPrediction(matches[0][0], round(matches[0][1], 3), "rules", alternatives)


def ml_prediction(description: str, rows: Iterable) -> CategoryPrediction:
    samples = [
        ((r.description or "").strip(), r.category)
        for r in rows
        if getattr(r, "amount", 0) < 0 and (r.description or "").strip() and (r.category or "").strip()
    ]
    category_counts = Counter(cat for _, cat in samples)
    if len(samples) < 8 or len(category_counts) < 2 or max(category_counts.values()) == len(samples):
        return rule_prediction(description)

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import MultinomialNB
        from sklearn.pipeline import make_pipeline
    except Exception:
        return rule_prediction(description)

    texts = [text for text, _ in samples]
    labels = [cat for _, cat in samples]
    model = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=1, strip_accents="unicode"),
        MultinomialNB(alpha=0.35),
    )
    try:
        model.fit(texts, labels)
        probs = model.predict_proba([description or ""])[0]
        classes = list(model.classes_)
    except Exception:
        return rule_prediction(description)

    ranked = sorted(zip(classes, probs), key=lambda item: item[1], reverse=True)
    alternatives = [{"category": cat, "confidence": round(float(prob), 3)} for cat, prob in ranked[:3]]
    top_cat, top_prob = ranked[0]
    if top_prob < 0.34:
        fallback = rule_prediction(description)
        fallback.alternatives = alternatives or fallback.alternatives
        return fallback
    return CategoryPrediction(top_cat, round(float(top_prob), 3), "ml", alternatives)
