import os
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files at /static
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

from fastapi.responses import FileResponse

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    user_input = data.get("input", "")
    if not user_input:
        return {"error": "No input provided"}

    def event_stream():
        response = openai.responses.create(
            model="gpt-4o-mini",
            instructions="You are Doctor Assist, a helpful assistant.",
            input=user_input,
            stream=True
        )
        for chunk in response:
            if hasattr(chunk, "model_dump"):
                data = chunk.model_dump()
            elif hasattr(chunk, "to_dict"):
                data = chunk.to_dict()
            else:
                data = str(chunk)
            yield f"data: {json.dumps(data)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000) 