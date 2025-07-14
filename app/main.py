import os
import uuid
from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = "asst_HqzPpB5b9orIeGk57kgeJkdJ"
openai = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files for local development only
if os.environ.get("VERCEL") is None and os.path.exists("public"):
    app.mount("/", StaticFiles(directory="public", html=True), name="public")

session_threads = {}
SESSION_COOKIE_NAME = "doctor_assist_session"

@app.post("/api/chat")
async def chat_endpoint(request: Request, response: Response, session_id: str = Cookie(None)):
    data = await request.json()
    user_input = data.get("input", "")
    if not user_input:
        return {"error": "No input provided"}

    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie(key=SESSION_COOKIE_NAME, value=session_id, httponly=True, samesite="lax")
    if session_id not in session_threads:
        thread = openai.beta.threads.create()
        session_threads[session_id] = thread.id
    thread_id = session_threads[session_id]

    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_input
    )

    def event_stream():
        run = openai.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
            stream=True
        )
        for chunk in run:
            if hasattr(chunk, "model_dump"):
                serializable_chunk = chunk.model_dump()
            elif hasattr(chunk, "dict"):
                serializable_chunk = chunk.dict()
            elif hasattr(chunk, "__dict__"):
                serializable_chunk = chunk.__dict__
            else:
                serializable_chunk = str(chunk)
            yield f"data: {json.dumps(serializable_chunk)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000) 