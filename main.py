import os
import logging
import uuid
import traceback
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
import json

# Load environment variables
load_dotenv()
SUPABASE_URL = "https://utigkgjcyqnrhpndzqhs.supabase.co"  # Hardcoded Supabase URL
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = "7583525993:AAG-T4zPD2LaomugUeyeUe7GvV4Kco_r4eg"

if not all([SUPABASE_KEY]):
    raise ValueError("Missing required environment variables. Please set SUPABASE_KEY")

# Log the Supabase URL for debugging
logger = logging.getLogger(__name__)
logger.info(f"Initialized with Supabase URL: {SUPABASE_URL}")

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize FastAPI
app = FastAPI()

# Conversation states
MARKET, INSTRUMENT, TIMEFRAME = range(3)

# Market options
MARKETS = {
    'forex': ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD'],
    'crypto': ['BTCUSD', 'ETHUSD', 'XRPUSD', 'DOTUSD', 'ADAUSD'],
    'commodities': ['XAUUSD', 'XAGUSD', 'WTIUSD', 'BRENTUSD'],
    'indices': ['US30', 'SPX500', 'NAS100', 'GER40']
}

TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']

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
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
        }
        
        # Construct URL parts carefully
        url = "https://utigkgjcyqnrhpndzqhs.supabase.co/rest/v1/subscribers"
        
        logger.info(f"Attempting to save data to Supabase at: {url}")
        logger.info(f"Request data: {data}")
        logger.info(f"Request headers: {headers}")
        
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.post(
                url,
                json=data,
                headers=headers
            )
            
            logger.info(f"Supabase response status: {response.status_code}")
            logger.info(f"Supabase response headers: {response.headers}")
            logger.info(f"Supabase response body: {response.text}")
            
            if response.status_code in [200, 201]:
                return {"success": True}
            else:
                logger.error(f"Unexpected status code: {response.status_code}")
                raise Exception(f"Database error: {response.text}")
                
    except Exception as e:
        logger.error(f"Error saving to Supabase: {str(e)}")
        logger.error(f"Full Supabase URL used: {url}")
        raise

async def query_supabase(instrument: str, timeframe: str) -> List[dict]:
    """Query Supabase for matching subscribers using direct HTTP request."""
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        }
        
        # Construct URL parts carefully
        url = "https://utigkgjcyqnrhpndzqhs.supabase.co/rest/v1/subscribers"
        
        logger.info(f"Attempting to query Supabase at: {url}")
        
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(
                url,
                headers=headers,
                params={
                    'select': '*',
                    'instrument': f'eq.{instrument}',
                    'timeframe': f'eq.{timeframe}'
                }
            )
            
            logger.info(f"Supabase response status: {response.status_code}")
            logger.info(f"Supabase response headers: {response.headers}")
            logger.info(f"Supabase response body: {response.text}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Unexpected status code: {response.status_code}")
                raise Exception(f"Database error: {response.text}")
                
    except Exception as e:
        logger.error(f"Error querying Supabase: {str(e)}")
        logger.error(f"Full Supabase URL used: {url}")
        raise

# Telegram bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for the market."""
    keyboard = [
        [InlineKeyboardButton("Forex", callback_data='market_forex')],
        [InlineKeyboardButton("Crypto", callback_data='market_crypto')],
        [InlineKeyboardButton("Commodities", callback_data='market_commodities')],
        [InlineKeyboardButton("Indices", callback_data='market_indices')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to SigmaPips! Select a market:",
        reply_markup=reply_markup
    )
    return MARKET

async def market_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle market selection and show instruments."""
    query = update.callback_query
    await query.answer()
    
    market = query.data.split('_')[1]
    context.user_data['market'] = market
    
    instruments = MARKETS[market]
    keyboard = [[InlineKeyboardButton(instr, callback_data=f'instrument_{instr}')] for instr in instruments]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Select {market} instrument:",
        reply_markup=reply_markup
    )
    return INSTRUMENT

async def instrument_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle instrument selection and show timeframes."""
    query = update.callback_query
    await query.answer()
    
    instrument = query.data.split('_')[1]
    context.user_data['instrument'] = instrument
    
    keyboard = [[InlineKeyboardButton(tf, callback_data=f'timeframe_{tf}')] for tf in TIMEFRAMES]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Select timeframe for {instrument}:",
        reply_markup=reply_markup
    )
    return TIMEFRAME

async def timeframe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle timeframe selection and save preferences."""
    query = update.callback_query
    await query.answer()
    
    timeframe = query.data.split('_')[1]
    context.user_data['timeframe'] = timeframe
    
    subscriber_data = {
        'subscriber_id': str(uuid.uuid4()),
        'market': context.user_data['market'],
        'instrument': context.user_data['instrument'],
        'timeframe': timeframe,
        'chat_id': str(update.effective_chat.id)
    }
    
    try:
        await save_to_supabase(subscriber_data)
        logger.info(f"Saved subscriber data: {subscriber_data}")
        await query.edit_message_text(
            f"Perfect! Your preferences have been saved.\n\n"
            f"Market: {subscriber_data['market']}\n"
            f"Instrument: {subscriber_data['instrument']}\n"
            f"Timeframe: {subscriber_data['timeframe']}\n\n"
            "You will receive signals when they match your preferences."
        )
    except Exception as e:
        logger.error(f"Error saving to Supabase: {e}")
        await query.edit_message_text(
            "Sorry, there was an error saving your preferences. Please try /start again."
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
        MARKET: [CallbackQueryHandler(market_callback, pattern='^market_')],
        INSTRUMENT: [CallbackQueryHandler(instrument_callback, pattern='^instrument_')],
        TIMEFRAME: [CallbackQueryHandler(timeframe_callback, pattern='^timeframe_')]
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
