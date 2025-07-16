import os
import uuid
from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import httpx
from dotenv import load_dotenv
import json

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID")

openai = OpenAI(api_key=OPENAI_API_KEY)


def get_price_and_date(item_name: str):
    """Retrieve price and date fields from Airtable for the given item."""
    if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_ID):
        return {"error": "Airtable environment variables not configured"}

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    params = {
        "filterByFormula": f"{{Name}}='{item_name}'",
        "maxRecords": 1,
    }
    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if not records:
            return {"price": None, "date": None}
        fields = records[0].get("fields", {})
        return {
            "price": fields.get("Price"),
            "date": fields.get("Date"),
        }
    except Exception as exc:
        return {"error": str(exc)}

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

    def serialize_chunk(chunk):
        if hasattr(chunk, "model_dump"):
            return chunk.model_dump()
        if hasattr(chunk, "dict"):
            return chunk.dict()
        if hasattr(chunk, "__dict__"):
            return chunk.__dict__
        return str(chunk)

    def stream_run(run_stream):
        for chunk in run_stream:
            yield f"data: {json.dumps(serialize_chunk(chunk))}\n\n"
            if chunk.event == "thread.run.requires_action":
                outputs = []
                for call in chunk.data.required_action.submit_tool_outputs.tool_calls:
                    if call.function.name == "get_price_and_date":
                        args = json.loads(call.function.arguments)
                        item = args.get("item") or args.get("name")
                        result = get_price_and_date(item)
                        outputs.append({"tool_call_id": call.id, "output": json.dumps(result)})
                if outputs:
                    follow_stream = openai.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=chunk.data.id,
                        tool_outputs=outputs,
                        stream=True
                    )
                    yield from stream_run(follow_stream)

    def event_stream():
        initial_stream = openai.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
            stream=True
        )
        yield from stream_run(initial_stream)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000) 