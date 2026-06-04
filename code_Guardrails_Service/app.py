from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Guardrails Mock Service")

# מבנה הבקשה (הטקסט שנרצה לבדוק)
class GuardrailsRequest(BaseModel):
    text: str

# מבנה התשובה (האם הטקסט בטוח או לא)
class GuardrailsResponse(BaseModel):
    is_safe: bool
    reason: str

@app.post("/check/input", response_model=GuardrailsResponse)
def check_input(request: GuardrailsRequest):
    # החזרה קבועה (Mock) שהקלט תקין
    return {"is_safe": True, "reason": "Input is safe and relevant."}

@app.post("/check/output", response_model=GuardrailsResponse)
def check_output(request: GuardrailsRequest):
    # החזרה קבועה (Mock) שהפלט תקין
    return {"is_safe": True, "reason": "Output contains no hallucinations or illegal claims."}

if __name__ == "__main__":
    import uvicorn
    # השירות הזה ירוץ על פורט 8003
    uvicorn.run(app, host="0.0.0.0", port=8003)