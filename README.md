# TradingView Subscriber Matcher

This service matches trading signals with subscribers based on instrument and timeframe preferences.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the service:
```bash
uvicorn main:app --reload
```

## API Endpoints

### POST /match-subscribers

Find subscribers that match a trading signal's instrument and timeframe.

Request body:
```json
{
    "instrument": "EURUSD",
    "timeframe": "1h"
}
```

Response:
```json
{
    "status": "success",
    "message": "Subscribers matched successfully",
    "data": {
        "match_info": {
            "instrument": "EURUSD",
            "timeframe": "1h"
        },
        "subscribers": [
            {
                "id": 1,
                "instrument": "EURUSD",
                "timeframe": "1h",
                "chat_id": "123456789"
            }
        ],
        "subscriber_count": 1
    }
}
