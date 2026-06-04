from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI(title="RAG Mock Service")

# הגדרת המבנה של הבקשה (הטקסט של המודעה שה-n8n ישלח)
class RAGRequest(BaseModel):
    property_description: str

# הגדרת המבנה של נכס דומה בודד
class SimilarProperty(BaseModel):
    id: int
    title: str
    price: int
    similarity_score: float

# אנדפוינט לחיפוש נכסים דומים
@app.post("/search", response_model=List[SimilarProperty])
def search_similar_properties(request: RAGRequest):
    # נחזיר נתוני דמי (Mock) של 3 נכסים קבועים כדי לבדוק את התשתית
    return [
        {"id": 101, "title": "3-room apartment in Central Haifa", "price": 1500000, "similarity_score": 0.89},
        {"id": 102, "title": "Cozy studio near University of Haifa", "price": 950000, "similarity_score": 0.82},
        {"id": 103, "title": "Renovated apartment with sea view", "price": 1800000, "similarity_score": 0.75}
    ]

if __name__ == "__main__":
    import uvicorn
    # השירות הזה ירוץ על פורט 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)