import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/api/test")
async def test_endpoint():
    try:
        # Test basic imports
        import json
        import asyncio
        from dotenv import load_dotenv
        
        # Test agents import
        try:
            from agents import Agent, Runner
            agents_ok = "✅ Agents SDK imported successfully"
        except Exception as e:
            agents_ok = f"❌ Agents SDK failed: {str(e)}"
        
        # Test airtable tools import
        try:
            import api.airtable_tools as airtable_tools
            airtable_ok = "✅ Airtable tools imported successfully"
        except Exception as e:
            airtable_ok = f"❌ Airtable tools failed: {str(e)}"
        
        # Test environment variables
        openai_key = os.getenv("OPENAI_API_KEY")
        vector_store = os.getenv("DOCTOR_ASSIST_VECTOR")
        airtable_key = os.getenv("AIRTABLE_API_KEY")
        
        env_status = {
            "OPENAI_API_KEY": "✅ Set" if openai_key else "❌ Missing",
            "DOCTOR_ASSIST_VECTOR": "✅ Set" if vector_store else "❌ Missing", 
            "AIRTABLE_API_KEY": "✅ Set" if airtable_key else "❌ Missing"
        }
        
        return JSONResponse({
            "status": "Test completed",
            "agents_import": agents_ok,
            "airtable_import": airtable_ok,
            "environment_variables": env_status
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "Test failed",
            "error": str(e)
        }) 