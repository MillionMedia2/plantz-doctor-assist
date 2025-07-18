import os
import uuid
from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import json
import asyncio
from agents import Agent, Runner
from agents.tool import FunctionTool, FileSearchTool
try:
    import api.airtable_tools as airtable_tools
except ImportError:
    # Create a mock airtable_tools module if import fails
    class MockAirtableTools:
        @staticmethod
        def get_product_prices(product_name):
            return f"No price data available for {product_name} (Airtable tools not available)"
        
        @staticmethod
        def filter_products(**kwargs):
            return "No products found (Airtable tools not available)"
        
        @staticmethod
        def get_latest_products(**kwargs):
            return "No latest products found (Airtable tools not available)"
    
    airtable_tools = MockAirtableTools()
from typing import Optional
from agents.models.openai_responses import OpenAIResponsesModel

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VECTOR_STORE_ID = os.getenv("DOCTOR_ASSIST_VECTOR") or ""

# Try to read instructions file, fallback to default if not found
try:
    INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "instructions", "doctor_assist.md")
    with open(INSTRUCTIONS_PATH, "r") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    # Fallback instructions if file not found
    SYSTEM_PROMPT = """You are Plantz Doctor Assist, a helpful and expert assistant in medical cannabis. Your role is to support licensed doctors in selecting the most appropriate cannabis-based products for their patients.

You must always retrieve information using the available tools. Do not guess, invent, or answer from your own training data. If no relevant information is found, politely explain that the data is not available.

When a doctor asks for a product recommendation:
1. Identify the patient's condition or symptom
2. Use the available tools to find relevant products
3. Recommend products that match the condition
4. If no products are found, ask the doctor to clarify

Always use the available tools for any factual question about products, prices, or medical uses."""

# Airtable tool wrappers
async def async_get_product_prices(ctx, args):
    if isinstance(args, str):
        args = json.loads(args)
    product_name = args.get("product_name")
    print(f"[DEBUG] get_product_prices called with: {product_name}")
    result = airtable_tools.get_product_prices(product_name)
    print(f"[DEBUG] get_product_prices result: {result}")
    return result

async def async_filter_products(ctx, args):
    if isinstance(args, str):
        args = json.loads(args)
    return airtable_tools.filter_products(
        product_type=args.get("product_type"),
        condition=args.get("condition"),
        min_price=args.get("min_price"),
        max_price=args.get("max_price"),
        limit=args.get("limit", 3)
    )

async def async_get_latest_products(ctx, args):
    if isinstance(args, str):
        args = json.loads(args)
    return airtable_tools.get_latest_products(
        days=args.get("days", 14),
        limit=args.get("limit", 3)
    )

get_product_prices_tool = FunctionTool(
    name="get_product_prices",
    description="Get all price/quantity options for a product by name. Use this tool for any question about the price, cost, how much, or value of a specific product. This includes any query where the user asks for the price, cost, or value, even if not using those exact words.",
    params_json_schema={
        "type": "object",
        "properties": {
            "product_name": {
                "type": "string",
                "description": "The name of the product to search for"
            }
        },
        "required": ["product_name"],
        "additionalProperties": False
    },
    on_invoke_tool=async_get_product_prices
)
filter_products_tool = FunctionTool(
    name="filter_products",
    description="Filter products by type, condition, and price range. Use this tool for any question about finding products within a certain price range, budget, affordable, expensive, or for comparing prices. This includes any query where the user asks for products by price, cost, or value, even if not using those exact words.",
    params_json_schema={
        "type": "object",
        "properties": {
            "product_type": {
                "type": "string",
                "description": "Type of product to filter by"
            },
            "condition": {
                "type": "string",
                "description": "Medical condition to filter by"
            },
            "min_price": {
                "type": "number",
                "description": "Minimum price filter"
            },
            "max_price": {
                "type": "number",
                "description": "Maximum price filter"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 3
            }
        },
        "required": ["product_type", "condition", "min_price", "max_price", "limit"],
        "additionalProperties": False
    },
    on_invoke_tool=async_filter_products
)
get_latest_products_tool = FunctionTool(
    name="get_latest_products",
    description="Get latest or new products created or modified in the last N days.",
    params_json_schema={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to look back for new/modified products",
                "default": 14
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 3
            }
        },
        "required": ["days", "limit"],
        "additionalProperties": False
    },
    on_invoke_tool=async_get_latest_products
)

# FileSearchTool for vector store retrieval
file_search_tool = FileSearchTool(
    vector_store_ids=[VECTOR_STORE_ID],
    max_num_results=3,
    include_search_results=True,
)

# Create OpenAI client
from openai import AsyncOpenAI
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Create the agent with all tools using the Responses API
agent = Agent(
    name="DoctorAssistAgent",
    model=OpenAIResponsesModel(model="gpt-4o-mini", openai_client=openai_client),
    tools=[file_search_tool, get_product_prices_tool, filter_products_tool, get_latest_products_tool],
    instructions=SYSTEM_PROMPT,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/chat")
async def chat_endpoint(request: Request, response: Response):
    try:
        print("[DEBUG] Chat endpoint called")
        data = await request.json()
        user_input = data.get("input", "")
        session_id = data.get("session") or str(uuid.uuid4())
        prev_response_id = data.get("previous_response_id")
        print(f"[DEBUG] Received session: {session_id}, previous_response_id: {prev_response_id}")
        if not user_input:
            return {"error": "No input provided"}
        print(f"[DEBUG] User input: {user_input}")
        assistant_id = None
        async def event_stream():
            nonlocal assistant_id
            try:
                from agents import SQLiteSession
                session_obj = SQLiteSession(session_id=session_id)
                result = Runner.run_streamed(agent, user_input, session=session_obj, previous_response_id=prev_response_id)
                from openai.types.responses import ResponseTextDeltaEvent
                from agents import ItemHelpers
                assistant_id = None
                first_delta = True
                async for event in result.stream_events():
                    print(f"[DEBUG] Event type: {event.type}")
                    
                    if (
                        event.type == "raw_response_event" 
                        and hasattr(event, 'data')
                        and isinstance(event.data, ResponseTextDeltaEvent)
                    ):
                        print(f"[DEBUG] Processing ResponseTextDeltaEvent")
                        # Convert to dict to access raw JSON fields
                        raw = event.data.to_dict()
                        delta_id = raw.get("item_id")  # Use "item_id" not "id"
                        print(f"[DEBUG] Raw delta data: {raw}")
                        print(f"[DEBUG] Delta ID: {delta_id}")
                        
                        # On the very first delta, grab the official ID
                        if first_delta and delta_id:
                            assistant_id = delta_id
                            print(f"[DEBUG] Captured assistant_id from first delta: {assistant_id}")
                            first_delta = False

                        # Always stream out the delta text
                        if event.data.delta:
                            yield f"data: {{\"event\": \"thread.message.delta\", \"data\": {{\"delta\": {{\"content\": [{{\"type\": \"text\", \"text\": {{\"value\": {json.dumps(event.data.delta)} }} }}] }} }} }}\n\n"
                    elif event.type == "run_item_stream_event":
                        if event.item.type == "message_output_item":
                            message_text = ItemHelpers.text_message_output(event.item)
                            print(f"[DEBUG] Final message: {message_text}")
                            print(f"[DEBUG] event.item: {event.item}")
                            # Fallback: Try to get ID from the message output item
                            if hasattr(event.item, 'raw_item') and hasattr(event.item.raw_item, 'id'):
                                assistant_id = event.item.raw_item.id
                                print(f"[DEBUG] Captured assistant_id from message output item: {assistant_id}")
                    elif event.type == "agent_updated_stream_event":
                        print(f"[DEBUG] Agent updated: {event.new_agent.name}")
                # After the stream, emit a message complete event
                yield f"data: {{\"event\":\"thread.message.complete\"}} \n\n"
                # Then emit the new previous_response_id
                if assistant_id:
                    print(f"[DEBUG] Emitting previous_response_id: {assistant_id}")
                    yield f"data: {{\"event\": \"previous_response_id\", \"data\": {{\"previous_response_id\": \"{assistant_id}\"}}}}\n\n"
                else:
                    print(f"[DEBUG] No assistant_id captured, cannot emit previous_response_id")
            except Exception as e:
                print(f"[DEBUG] Exception in event_stream: {e}")
                import traceback
                traceback.print_exc()
                yield f"data: {{\"event\": \"error\", \"data\": {{\"error\": {json.dumps(str(e))} }} }}\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Internal server error: {str(e)}"}

# Serve static files for local development only (after all API routes)
if os.environ.get("VERCEL") is None and os.path.exists("public"):
    app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000) 