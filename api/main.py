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

# Create the agent with all tools
try:
    agent = Agent(
        name="DoctorAssistAgent",
        instructions=SYSTEM_PROMPT,
        tools=[file_search_tool, get_product_prices_tool, filter_products_tool, get_latest_products_tool],
        model="gpt-4.1-mini",
    )
except Exception as e:
    print(f"Error creating agent: {e}")
    # Create a minimal agent without tools if creation fails
    agent = Agent(
        name="DoctorAssistAgent",
        instructions=SYSTEM_PROMPT,
        tools=[],
        model="gpt-4.1-mini",
    )

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Preprocessing step: nudge agent for price-related queries
def nudge_for_price(input_text: str) -> str:
    price_keywords = ["price", "cost", "how much", "affordable", "expensive", "budget", "value", "cheapest", "most expensive"]
    lowered = input_text.lower()
    if any(keyword in lowered for keyword in price_keywords):
        return f"[USER QUERY INVOLVES PRICE] {input_text}"
    return input_text

@app.post("/api/chat")
async def chat_endpoint(request: Request, response: Response, previous_response_id: Optional[str] = Cookie(None)):
    try:
        data = await request.json()
        user_input = data.get("input", "")
        # Prefer previous_response_id from request body if present
        prev_id = data.get("previous_response_id") or previous_response_id
        if not user_input:
            return {"error": "No input provided"}
        # Preprocess user input to nudge agent for price-related queries
        user_input = nudge_for_price(user_input)
        new_response_id = None
        async def event_stream():
            nonlocal new_response_id
            try:
                # Pass previous_response_id to Runner.run_streamed
                result = Runner.run_streamed(agent, user_input, previous_response_id=prev_id)
                from openai.types.responses import ResponseTextDeltaEvent
                from agents import ItemHelpers
                async for event in result.stream_events():
                    # Stream token-by-token deltas only
                    if event.type == "raw_response_event":
                        if hasattr(event, "data") and isinstance(event.data, ResponseTextDeltaEvent):
                            delta = event.data.delta
                            if delta:
                                yield f"data: {{\"event\": \"thread.message.delta\", \"data\": {{\"delta\": {{\"content\": [{{\"type\": \"text\", \"text\": {{\"value\": {json.dumps(delta)} }} }}] }} }} }}\n\n"
                    # Log the final message for debugging, but do not yield to frontend
                    elif event.type == "run_item_stream_event":
                        if event.item.type == "message_output_item":
                            message_text = ItemHelpers.text_message_output(event.item)
                            print(f"[DEBUG] Final message: {message_text}")
                            print(f"[DEBUG] event.item: {event.item}")
                            # Capture the new response_id for session tracking (to be updated after debugging)
                            # if hasattr(event.item, 'response_id'):
                            #     new_response_id = event.item.response_id
                    elif event.type == "agent_updated_stream_event":
                        print(f"[DEBUG] Agent updated: {event.new_agent.name}")
            except Exception as e:
                print(f"[DEBUG] Exception in event_stream: {e}")
                import traceback
                traceback.print_exc()
                yield f"data: {{\"event\": \"error\", \"data\": {{\"error\": {json.dumps(str(e))} }} }}\n\n"
        # Stream the response and set the cookie after the run
        streaming_response = StreamingResponse(event_stream(), media_type="text/event-stream")
        # Set the cookie after the run (FastAPI limitation: must set before returning, so we use a workaround)
        async def set_cookie_and_return():
            async for chunk in streaming_response.body_iterator:
                if new_response_id:
                    response.set_cookie(key="previous_response_id", value=new_response_id, httponly=True)
                yield chunk
        return StreamingResponse(set_cookie_and_return(), media_type="text/event-stream")
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