import os
import json
import logging
import traceback
from typing import Optional, List
from fastapi import FastAPI
from pydantic import BaseModel
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase configuratie
SUPABASE_URL = 'https://utigkgjcyqnrhpndzqhs.supabase.co/rest/v1/subscribers'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV0aWdrZ2pjeXFucmhwbmR6cWhzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNjMyMzA1NiwiZXhwIjoyMDUxODk5MDU2fQ.8JovzmGQofC4oC2016P7aa6FZQESF3UNSjUTruIYWbg'

# n8n webhook URL
N8N_WEBHOOK_URL = "https://primary-production-007c.up.railway.app/webhook-test/c10fba2b-0fbd-471f-9db1-907c1c754802"

app = FastAPI()

class SignalMatch(BaseModel):
    instrument: str
    timeframe: str

async def get_subscribers(instrument: str, timeframe: str) -> List[dict]:
    """Haal subscribers op uit Supabase die matchen met het instrument en timeframe."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}?select=*&instrument=eq.{instrument}&timeframe=eq.{timeframe}",
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json'
            }
        )
        response.raise_for_status()
        return response.json()

@app.post("/match-subscribers")
async def match_subscribers(signal: SignalMatch) -> dict:
    """Find matching subscribers for a signal."""
    try:
        logger.info(f"Finding subscribers for {signal.instrument} {signal.timeframe}")
        
        # Get matching subscribers from Supabase
        subscribers = await get_subscribers(signal.instrument, signal.timeframe)
        logger.info(f"Found {len(subscribers)} matching subscribers")
        
        # Prepare webhook data
        webhook_data = {
            "match_info": {
                "instrument": signal.instrument,
                "timeframe": signal.timeframe,
            },
            "subscribers": subscribers,
            "subscriber_count": len(subscribers)
        }
        
        # Send to n8n webhook
        try:
            logger.info(f"Sending data to webhook: {N8N_WEBHOOK_URL}")
            async with httpx.AsyncClient() as client:
                response = await client.post(N8N_WEBHOOK_URL, json=webhook_data)
                logger.info(f"Webhook response status: {response.status_code}")
                logger.info(f"Webhook response content: {response.text}")
                response.raise_for_status()
            logger.info(f"Successfully sent data to n8n webhook")
        except Exception as e:
            logger.error(f"Failed to send data to n8n webhook: {str(e)}")
            
        return {
            "status": "success",
            "message": "Subscribers matched successfully",
            "data": webhook_data
        }
        
    except Exception as e:
        logger.error(f"Error matching subscribers: {str(e)}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        raise
