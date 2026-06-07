import json
import os
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

LISTINGS_PATH = Path(__file__).parent / "data" / "listings.json"
TOP_K = 5


def _listing_document(listing: dict) -> str:
    parts = [
        listing.get("title", ""),
        listing.get("description", ""),
        listing.get("city", ""),
        listing.get("neighborhood", ""),
        listing.get("property_type", ""),
        listing.get("deal", ""),
        " ".join(listing.get("features", [])),
        str(listing.get("rooms", "")),
        str(listing.get("price", "")),
        str(listing.get("size_sqm", "")),
    ]
    return " ".join(p for p in parts if p)


class ListingIndex:
    def __init__(self):
        self.listings: list[dict] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None

    def load(self, path: Path | None = None) -> None:
        listings_file = path or LISTINGS_PATH
        with open(listings_file, encoding="utf-8") as f:
            self.listings = json.load(f)
        documents = [_listing_document(item) for item in self.listings]
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            max_features=8000,
        )
        self.matrix = self.vectorizer.fit_transform(documents)

    def search(self, description: str, top_k: int = TOP_K) -> list[dict]:
        if not self.listings or self.vectorizer is None or self.matrix is None:
            return []
        query_vec = self.vectorizer.transform([description])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        ranked = sorted(
            enumerate(scores),
            key=lambda pair: pair[1],
            reverse=True,
        )[:top_k]
        results = []
        for idx, score in ranked:
            if score <= 0:
                continue
            listing = dict(self.listings[idx])
            listing["similarity_score"] = round(float(score), 4)
            results.append(listing)
        return results


def rule_based_insight(description: str, similar: list[dict]) -> str:
    if not similar:
        return "לא נמצאו נכסים דומים במאגר. נסו לפרט עיר, מספר חדרים או תקציב."

    top = similar[0]
    deal_he = "להשכרה" if top.get("deal") == "rent" else "למכירה"
    lines = [
        f"נמצאו {len(similar)} נכסים דומים לפי התיאור.",
        f"ההתאמה הטובה ביותר: {top.get('title')} ({top.get('city')}) — {deal_he}, "
        f"מחיר {top.get('price'):,}, ציון דמיון {top.get('similarity_score', 0):.2f}.",
    ]
    if len(similar) > 1:
        others = ", ".join(s.get("city", "") for s in similar[1:3])
        lines.append(f"אפשרויות נוספות באזורים: {others}.")
    return " ".join(lines)


def ollama_insight(description: str, similar: list[dict]) -> str | None:
    import requests

    ollama_url = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3")
    summary = json.dumps(similar[:3], ensure_ascii=False, indent=2)
    prompt = (
        "You are a real-estate analyst. In 2-3 Hebrew sentences, summarize how the "
        "similar listings relate to the user query. Do not invent prices.\n\n"
        f"User query: {description}\n\nSimilar listings:\n{summary}"
    )
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=int(os.getenv("OLLAMA_INSIGHT_TIMEOUT", "5")),
        )
        if response.status_code == 200:
            text = response.json().get("response", "").strip()
            return text or None
    except Exception:
        pass
    return None


def generate_insight(description: str, similar: list[dict]) -> str:
    llm_text = ollama_insight(description, similar)
    if llm_text:
        return llm_text
    return rule_based_insight(description, similar)
