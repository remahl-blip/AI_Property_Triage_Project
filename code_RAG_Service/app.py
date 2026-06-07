import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from rag_engine import ListingIndex, generate_insight

index = ListingIndex()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    index.load()
    print(f"RAG index ready with {len(index.listings)} listings.")
    yield


app = FastAPI(title="RAG Service (Layer 3)", lifespan=lifespan)


class QueryRequest(BaseModel):
    description: str = Field(..., min_length=1)


class QueryResponse(BaseModel):
    similar_listings: list[dict]
    insight: str


@app.post("/query", response_model=QueryResponse)
def query_listings(request: QueryRequest):
    similar = index.search(request.description.strip())
    insight = generate_insight(request.description.strip(), similar)
    return {"similar_listings": similar, "insight": insight}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "layer": 3,
        "service": "rag",
        "listings_indexed": len(index.listings),
        "ollama_url": os.getenv("OLLAMA_URL", "http://host.docker.internal:11434"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
