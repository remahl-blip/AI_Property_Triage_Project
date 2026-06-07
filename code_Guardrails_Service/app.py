from fastapi import FastAPI
from pydantic import BaseModel

from guardrails_engine import GuardrailsResponse, check_input_text, check_output_text

app = FastAPI(title="Guardrails Service (Layer 3)")


class GuardrailsRequest(BaseModel):
    text: str


@app.post("/check/input", response_model=GuardrailsResponse)
def check_input(request: GuardrailsRequest):
    return check_input_text(request.text)


@app.post("/check/output", response_model=GuardrailsResponse)
def check_output(request: GuardrailsRequest):
    return check_output_text(request.text)


@app.get("/health")
def health():
    return {"status": "ok", "layer": 3, "service": "guardrails"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)
