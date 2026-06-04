from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="LangGraph Agent Mock Service")

# מבנה הבקשה מה-n8n (הודעת המשתמש וההיסטוריה)
class AgentRequest(BaseModel):
    user_message: str
    chat_history: list = []

# מבנה התשובה של הסוכן
class AgentResponse(BaseModel):
    agent_response: str
    status: str

@app.post("/chat", response_model=AgentResponse)
def chat_with_agent(request: AgentRequest):
    # החזרה קבועה (Mock) שמדמה את תשובת הסוכן החכם
    return {
        "agent_response": "Hello! I received your request regarding the property. Based on the data, I am analyzing the match for you.",
        "status": "success"
    }

if __name__ == "__main__":
    import uvicorn
    # השירות הזה ירוץ על פורט 8004
    uvicorn.run(app, host="0.0.0.0", port=8004)