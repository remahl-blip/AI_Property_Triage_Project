"""Pre-populate ChromaDB vector store with property listings (≥20 required)."""

import json
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from rag_engine import LISTINGS_PATH, CHROMA_PATH, _listing_document

MIN_LISTINGS = 20


def main():
    with open(LISTINGS_PATH, encoding="utf-8") as f:
        listings = json.load(f)

    if len(listings) < MIN_LISTINGS:
        raise SystemExit(f"Need at least {MIN_LISTINGS} listings, found {len(listings)}")

    if CHROMA_PATH.exists():
        shutil.rmtree(CHROMA_PATH)
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    docs = [
        Document(
            page_content=_listing_document(item),
            metadata={"id": item["id"], "listing": json.dumps(item, ensure_ascii=False)},
        )
        for item in listings
    ]
    Chroma.from_documents(docs, embedding=embeddings, persist_directory=str(CHROMA_PATH))
    print(f"Indexed {len(listings)} listings into {CHROMA_PATH}")


if __name__ == "__main__":
    main()
