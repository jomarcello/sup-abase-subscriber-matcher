import os
import logging
import uuid
import traceback
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = "7583525993:AAG-T4zPD2LaomugUeyeUe7GvV4Kco_r4eg"

if not all([SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("Missing required environment variables. Please set SUPABASE_URL and SUPABASE_KEY")

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI()

# Conversation states
MARKET, INSTRUMENT, TIMEFRAME = range(3)

# Data models
class SignalMatch(BaseModel):
    instrument: str
    timeframe: str

class TelegramData(BaseModel):
    chat_id: str
    market: str
    instrument: str
    timeframe: str

async def save_to_supabase(data: dict) -> dict:
    """Save data to Supabase using direct HTTP request."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/subscribers"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error saving to Supabase: {str(e)}")
        raise

async def query_supabase(instrument: str, timeframe: str) -> List[dict]:
    """Query Supabase for matching subscribers using direct HTTP request."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/subscribers?instrument=eq.{instrument}&timeframe=eq.{timeframe}"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error querying Supabase: {str(e)}")
        raise

# Telegram bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for the market."""
    await update.message.reply_text(
        "Welcome! Let's set up your trading preferences.\n\n"
        "First, which market are you interested in?\n"
        "Please type either 'forex' or 'crypto'"
    )
    return MARKET

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the market and ask for instrument."""
    user_market = update.message.text.lower()
    if user_market not in ['forex', 'crypto']:
        await update.message.reply_text(
            "Please enter either 'forex' or 'crypto'"
        )
        return MARKET
    
    context.user_data['market'] = user_market
    
    if user_market == 'forex':
        message = "Please enter the forex pair you want to trade (e.g., EURUSD, GBPUSD)"
    else:
        message = "Please enter the cryptocurrency pair you want to trade (e.g., BTCUSD, ETHUSD)"
    
    await update.message.reply_text(message)
    return INSTRUMENT

async def instrument(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the instrument and ask for timeframe."""
    context.user_data['instrument'] = update.message.text.upper()
    await update.message.reply_text(
        "What timeframe would you like to trade?\n"
        "Please enter one of: 1m, 5m, 15m, 30m, 1h, 4h, 1d"
    )
    return TIMEFRAME

async def timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the timeframe and save all data."""
    user_timeframe = update.message.text.lower()
    valid_timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
    
    if user_timeframe not in valid_timeframes:
        await update.message.reply_text(
            f"Please enter a valid timeframe: {', '.join(valid_timeframes)}"
        )
        return TIMEFRAME
    
    context.user_data['timeframe'] = user_timeframe
    
    # Save to Supabase
    subscriber_data = {
        'subscriber_id': str(uuid.uuid4()),
        'market': context.user_data['market'],
        'instrument': context.user_data['instrument'],
        'timeframe': context.user_data['timeframe'],
        'chat_id': str(update.effective_chat.id)
    }
    
    try:
        await save_to_supabase(subscriber_data)
        logger.info(f"Saved subscriber data: {subscriber_data}")
        await update.message.reply_text(
            "Perfect! Your preferences have been saved. "
            "You will now receive signals for "
            f"{subscriber_data['instrument']} on the {subscriber_data['timeframe']} timeframe."
        )
    except Exception as e:
        logger.error(f"Error saving to Supabase: {e}")
        await update.message.reply_text(
            "Sorry, there was an error saving your preferences. Please try again later."
        )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text('Setup cancelled. Type /start to begin again.')
    return ConversationHandler.END

# Initialize bot and add handlers
application = Application.builder().token(TELEGRAM_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, market)],
        INSTRUMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, instrument)],
        TIMEFRAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, timeframe)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

application.add_handler(conv_handler)

# FastAPI endpoints
@app.post("/match-subscribers")
async def match_subscribers(signal: SignalMatch) -> dict:
    """Match a trading signal with subscribers."""
    try:
        logger.info(f"Finding subscribers for {signal.instrument} {signal.timeframe}")
        
        # Query Supabase for matching subscribers
        subscribers = await query_supabase(signal.instrument, signal.timeframe)
        logger.info(f"Found {len(subscribers)} matching subscribers")
        
        return {
            "status": "success",
            "message": "Subscribers matched successfully",
            "data": {
                "match_info": signal.dict(),
                "subscribers": subscribers,
                "subscriber_count": len(subscribers)
            }
        }
        
    except Exception as e:
        logger.error(f"Error matching subscribers: {str(e)}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# Start bot polling in the background
@app.on_event("startup")
async def startup_event():
    """Start the Telegram bot when the FastAPI app starts."""
    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Telegram bot started successfully")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop the Telegram bot when the FastAPI app stops."""
    try:
        await application.stop()
        await application.shutdown()
        logger.info("Telegram bot stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping Telegram bot: {e}")
