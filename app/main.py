import os
import uuid
from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import StreamingResponse, FileResponse
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

# Serve public files at /public for local development and Vercel
# app.mount("/public", StaticFiles(directory="public", html=True), name="public")

@app.get("/")
def root():
    return FileResponse("public/index.html")

# In-memory session_id -> thread_id mapping
session_threads = {}
SESSION_COOKIE_NAME = "doctor_assist_session"

@app.post("/api/chat")
async def chat_endpoint(request: Request, response: Response, session_id: str = Cookie(None)):
    data = await request.json()
    user_input = data.get("input", "")
    if not user_input:
        return {"error": "No input provided"}

    # Session management
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie(key=SESSION_COOKIE_NAME, value=session_id, httponly=True, samesite="lax")
    
    # Thread management
    if session_id not in session_threads:
        thread = openai.beta.threads.create()
        session_threads[session_id] = thread.id
    thread_id = session_threads[session_id]

    # Add user message to thread
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_input
    )

    # Run the assistant and stream response
    def event_stream():
        print("Started streaming run...")
        run = openai.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
            stream=True
        )
        for chunk in run:
            print("Got chunk:", chunk)
            # Ensure chunk is JSON serializable
            if hasattr(chunk, "model_dump"):
                serializable_chunk = chunk.model_dump()
            elif hasattr(chunk, "dict"):
                serializable_chunk = chunk.dict()
            elif hasattr(chunk, "__dict__"):
                serializable_chunk = chunk.__dict__
            else:
                serializable_chunk = str(chunk)
            yield f"data: {json.dumps(serializable_chunk)}\n\n"
        print("Finished streaming run.")

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000) 