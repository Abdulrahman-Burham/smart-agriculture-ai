import os
import requests
import datetime
from duckduckgo_search import DDGS
from typing import Dict, Any, List

def get_weather(lat: float = 30.0444, lon: float = 31.2357) -> Dict[str, Any]:
    """Get current weather using Open-Meteo (100% Free, No API Key needed). Default is Cairo coordinates."""
    try:
        # Open-Meteo free API
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current_weather", {})
        
        return {
            "temperature": current.get("temperature"),
            "wind_speed": current.get("windspeed"),
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}

def search_web(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """Search the web for real-time agricultural information using DuckDuckGo."""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(f"{query} زراعة مبيدات", max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "url": r.get("href", "")
                })
        return results
    except Exception as e:
        print(f"Web search error: {e}")
        return []

def get_current_date_context() -> str:
    """Returns the current date and season to inject into the LLM prompt."""
    now = datetime.datetime.now()
    month = now.month
    
    season = "الصيف"
    if 3 <= month <= 5:
        season = "الربيع"
    elif 9 <= month <= 11:
        season = "الخريف"
    elif month == 12 or month <= 2:
        season = "الشتاء"
        
    return f"اليوم هو {now.strftime('%Y-%m-%d')}، ونحن الآن في فصل {season}."
