import streamlit as st
import requests
import json
import pandas as pd
import hashlib
from datetime import datetime

# Document-based constants
OPENROUTER_MODEL = "moonshotai/kimi-k2:free"

st.set_page_config(page_title="AI Trading Assistant (ICICI Breeze)", layout="wide")
st.title("📈 AI Trading Assistant (ICICI Breeze API)")

# Secrets loading
BREEZE_API_KEY = st.secrets["BREEZE_API_KEY"]
BREEZE_API_SECRET = st.secrets["BREEZE_API_SECRET"]
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# User input for session token (document: must be obtained via CustomerDetails API)
icici_session_token = st.text_input("ICICI Breeze Session Token", type="password")

# Stock mapping (document examples use stock codes like "ITC", "CNXBAN", "NIFTY")
STOCKS = {
    "RELIANCE": "RELIANCE",
    "TCS": "TCS", 
    "INFY": "INFY",
    "HDFCBANK": "HDFCBANK",
    "ICICIBANK": "ICICIBANK"
}

# Document: Supported exchanges are NSE, NFO (BSE and MCX not available per document)
EXCHANGES = ["NSE", "NFO"]
selected_exchange = st.selectbox("Select Exchange", options=EXCHANGES, index=0)
selected_stock = st.selectbox("Select Stock", options=list(STOCKS.keys()))
data_type = st.selectbox("Select Data Type", options=["LTP", "OHLC", "Volume", "Raw JSON"])
analyze = st.button("Analyze Market")

# Document-compliant checksum generation
def generate_checksum(timestamp: str, payload: str, secret_key: str) -> str:
    """
    Per document: Checksum is computed via SHA256 hash (Time Stamp + JSON Post Data + secret_key)
    """
    hash_str = timestamp + payload + secret_key
    return hashlib.sha256(hash_str.encode("utf-8")).hexdigest()

# Document-compliant market data fetcher
def fetch_market_data_icici(symbol: str, exchange: str, session_token: str,
                            api_key: str, api_secret: str):
    """
    Calls /breezeapi/api/v1/quotes per document specification
    """
    if not session_token:
        st.error("❌ Session token required")
        return None

    # Document: Required parameters for /quotes endpoint
    # For cash product, expiry_date, right, strike_price are optional
    payload_dict = {
        "stock_code": symbol,
        "exchange_code": exchange,
        "product_type": "cash",
        "right": "Others",
        "strike_price": "0"
    }
    # Document: "All JSON Data should be stringified before sending"
    # Must use separators=(',', ':') to ensure no spaces
    payload_str = json.dumps(payload_dict, separators=(",", ":"))

    # Document: ISO8601 UTC DateTime Format with 0 milliseconds
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Document: Checksum computation
    checksum = generate_checksum(timestamp, payload_str, api_secret)

    # Document: Request Headers
    headers = {
        "Content-Type": "application/json",
        "X-Checksum": f"token {checksum}",  # Document format: "token <checksum>"
        "X-Timestamp": timestamp,
        "X-AppKey": api_key,
        "X-SessionToken": session_token
    }

    # Document: Endpoint URL (no trailing spaces)
    url = "https://api.icicidirect.com/breezeapi/api/v1/quotes"

    try:
        # Document: GET request with JSON body
        resp = requests.get(url, headers=headers, data=payload_str, timeout=10)
        resp.raise_for_status()
        
        data = resp.json()
        
        # Document: Status 200 indicates success
        if data.get("Status") == 200:
            return data.get("Success")
        else:
            st.error(f"❌ API Error: {data.get('Error')}")
            return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ HTTP Error: {e}")
        st.error(f"Status Code: {e.response.status_code if e.response else 'N/A'}")
        return None
    except Exception as e:
        st.error(f"❌ Request failed: {e}")
        return None

# AI LLM function (not from ICICI doc, kept for app functionality)
def ask_llm(market_data):
    prompt = f"""
You are an expert trading analyst.

Market Data:
{json.dumps(market_data, indent=2)}

Return:
1. Trend
2. Momentum
3. Support & Resistance
4. Risk Level
5. Clear Buy / Sell / Hold

Be short, decisive, and practical.
"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a professional trading assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        st.error(f"❌ AI insight failed: {e}")
        return None

# Main flow
if analyze:
    with st.spinner("📡 Fetching market data..."):
        market_data = fetch_market_data_icici(
            STOCKS[selected_stock],
            selected_exchange,
            icici_session_token,
            BREEZE_API_KEY,
            BREEZE_API_SECRET
        )

    if market_data:
        st.subheader(f"📊 Market Data for {selected_stock} ({selected_exchange})")

        # Handle response format (document shows array of objects)
        if isinstance(market_data, list) and len(market_data) > 0:
            data = market_data[0]
        else:
            data = market_data

        if data_type == "Raw JSON":
            st.json(market_data)
        elif data_type == "LTP":
            ltp = data.get('ltp', 'N/A')
            st.metric("Last Traded Price", f"₹{ltp}")
        elif data_type == "Volume":
            volume = data.get('total_quantity_traded', 'N/A')
            st.metric("Volume", f"{volume:,}" if isinstance(volume, (int, float)) else volume)
        elif data_type == "OHLC":
            ohlc = {
                'Open': data.get('open'),
                'High': data.get('high'),
                'Low': data.get('low'),
                'Close': data.get('close'),
                'Previous Close': data.get('previous_close')
            }
            st.dataframe(pd.DataFrame([ohlc]))

        # AI analysis (app feature, not part of ICICI doc)
        with st.spinner("🧠 AI analyzing..."):
            insight = ask_llm(market_data)

        if insight:
            st.subheader("🤖 AI Trading Insight")
            st.markdown(insight)
