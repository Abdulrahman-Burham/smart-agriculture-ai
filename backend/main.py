import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag.respond import RAGPipeline
from rag.generate import GroqLLMProvider
from rag.tools import get_weather, get_current_date_context

load_dotenv()

app = FastAPI(title="Egyptian Agriculture AI Assistant")

# Initialize Pipeline once on startup
pipeline = RAGPipeline(config_path="rag/config.yaml", lexicon_path="rag/lexicon.json")
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY not found in .env")
pipeline.llm_provider = GroqLLMProvider(api_key=api_key)

class ChatRequest(BaseModel):
    query: str
    location: str = "Cairo"  # Default location

class ChatResponse(BaseModel):
    answer: str
    weather: str
    sources: list

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Get dynamic context (Time, Season, Weather)
        date_context = get_current_date_context()
        weather_data = get_weather() # Getting default for now or we could use request.location
        
        weather_str = ""
        if weather_data.get("status") == "success":
            weather_str = f"درجة الحرارة المتوقعة: {weather_data.get('temperature')}°C، سرعة الرياح: {weather_data.get('wind_speed')} كم/س."
        
        # We inject this context directly into the query for the RAG pipeline to be aware
        enriched_query = f"{request.query} \n(معلومة للمساعد: {date_context} {weather_str})"
        
        # Run RAG
        result = pipeline.run(enriched_query)
        
        sources = [
            f"صفحة {c.get('metadata', {}).get('page_start', '?')}" 
            for c in result.get("sources", [])
        ]
        
        return ChatResponse(
            answer=result["answer"],
            weather=weather_str,
            sources=list(set(sources)) # Unique pages
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount frontend directory for static files (CSS, JS if needed)
os.makedirs("frontend", exist_ok=True)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")
