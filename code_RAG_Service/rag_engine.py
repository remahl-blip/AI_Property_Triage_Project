"""RAG engine: LangChain + ChromaDB + HuggingFace embeddings + Ollama insight."""

import json
import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings

LISTINGS_PATH = Path(__file__).parent / "data" / "listings.json"
CHROMA_PATH = Path(__file__).parent / "data" / "chroma_db"
TOP_K = 3

RAG_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a real-estate analyst. Use ONLY the retrieved listing context below. "
        "Cite listing IDs you reference. Do not invent prices or features. "
        "Respond in 2-3 Hebrew sentences.",
    ),
    ("human", "User query: {query}\n\nRetrieved listings:\n{context}"),
])


def _listing_document(listing: dict) -> str:
    parts = [
        f"id={listing.get('id')}",
        listing.get("title", ""),
        listing.get("description", ""),
        f"city={listing.get('city')}",
        f"neighborhood={listing.get('neighborhood', '')}",
        f"type={listing.get('property_type')}",
        f"deal={listing.get('deal')}",
        f"rooms={listing.get('rooms')}",
        f"price={listing.get('price')}",
        f"sqm={listing.get('size_sqm')}",
        "features=" + ", ".join(listing.get("features", [])),
    ]
    return " | ".join(p for p in parts if p)


class ListingRAG:
    def __init__(self):
        self.listings: list[dict] = []
        self.vectorstore: Chroma | None = None
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
        )

    def load_listings(self, path: Path | None = None) -> None:
        listings_file = path or LISTINGS_PATH
        with open(listings_file, encoding="utf-8") as f:
            self.listings = json.load(f)

    def build_or_load_index(self) -> None:
        self.load_listings()
        docs = [
            Document(
                page_content=_listing_document(item),
                metadata={"id": item.get("id", ""), "listing": json.dumps(item, ensure_ascii=False)},
            )
            for item in self.listings
        ]
        if CHROMA_PATH.exists():
            self.vectorstore = Chroma(
                persist_directory=str(CHROMA_PATH),
                embedding_function=self.embeddings,
            )
        else:
            CHROMA_PATH.mkdir(parents=True, exist_ok=True)
            self.vectorstore = Chroma.from_documents(
                documents=docs,
                embedding=self.embeddings,
                persist_directory=str(CHROMA_PATH),
            )

    def search(self, description: str, top_k: int = TOP_K) -> list[dict]:
        if not self.vectorstore:
            return []
        results = self.vectorstore.similarity_search_with_score(description, k=top_k)
        similar = []
        for doc, distance in results:
            try:
                listing = json.loads(doc.metadata.get("listing", "{}"))
            except json.JSONDecodeError:
                listing = {"id": doc.metadata.get("id"), "snippet": doc.page_content}
            listing["similarity_score"] = round(max(0, 1 - float(distance)), 4)
            similar.append(listing)
        return similar


def rule_based_insight(description: str, similar: list[dict]) -> str:
    if not similar:
        return "לא נמצאו נכסים דומים במאגר. נסו לפרט עיר, מספר חדרים או תקציב."
    top = similar[0]
    deal_he = "להשכרה" if top.get("deal") == "rent" else "למכירה"
    cited = ", ".join(s.get("id", "?") for s in similar[:3])
    return (
        f"נמצאו {len(similar)} נכסים דומים (מזהים: {cited}). "
        f"ההתאמה הטובה ביותר: {top.get('title')} ב{top.get('city')} — {deal_he}, "
        f"מחיר {top.get('price'):,}, ציון דמיון {top.get('similarity_score', 0):.2f}."
    )


def ollama_insight(description: str, similar: list[dict]) -> str | None:
    import requests

    ollama_url = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3")
    context = "\n".join(
        f"- {s.get('id')}: {s.get('title')} | {s.get('city')} | {s.get('price')} ₪"
        for s in similar[:3]
    )
    messages = RAG_PROMPT.format_messages(query=description, context=context)
    system = messages[0].content if messages else ""
    user = messages[1].content if len(messages) > 1 else description
    try:
        response = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
            },
            timeout=int(os.getenv("OLLAMA_INSIGHT_TIMEOUT", "30")),
        )
        if response.status_code == 200:
            text = response.json().get("message", {}).get("content", "").strip()
            return text or None
    except Exception:
        pass
    return None


def generate_insight(description: str, similar: list[dict]) -> str:
    llm_text = ollama_insight(description, similar)
    if llm_text:
        return llm_text
    return rule_based_insight(description, similar)


# Module-level singleton
_index: ListingRAG | None = None


def get_index() -> ListingRAG:
    global _index
    if _index is None:
        _index = ListingRAG()
        _index.build_or_load_index()
    return _index
