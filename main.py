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

# Load environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL')

if not all([SUPABASE_URL, SUPABASE_KEY, N8N_WEBHOOK_URL]):
    raise ValueError("Missing required environment variables. Please set SUPABASE_URL, SUPABASE_KEY, and N8N_WEBHOOK_URL")

app = FastAPI()

class SignalMatch(BaseModel):
    instrument: str
    timeframe: str

async def get_subscribers(instrument: str, timeframe: str) -> List[dict]:
    """Haal subscribers op uit Supabase die matchen met het instrument en timeframe."""
    try:
        logger.info(f"SUPABASE_URL: {SUPABASE_URL}")  
        logger.info(f"Making request to Supabase for {instrument} {timeframe}")
        
        url = f"{SUPABASE_URL}?select=*&instrument=eq.{instrument}&timeframe=eq.{timeframe}"
        logger.info(f"Full URL: {url}")  
        
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        logger.info("Headers prepared (key hidden)")  
        
        async with httpx.AsyncClient(verify=False) as client:  
            response = await client.get(url, headers=headers)
            logger.info(f"Response status: {response.status_code}")  
            logger.info(f"Response content: {response.text}")  
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error in get_subscribers: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        raise

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
