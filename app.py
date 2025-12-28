import streamlit as st
import requests
import json
import pandas as pd
import hashlib
from datetime import datetime

# --------------------------------
# CONFIG
# --------------------------------
OPENROUTER_MODEL = "moonshotai/kimi-k2:free"

st.set_page_config(page_title="AI Trading Assistant (ICICI Breeze)", layout="wide")
st.title("📈 AI Trading Assistant (ICICI Breeze API)")

# --------------------------------
# SECRETS
# --------------------------------
BREEZE_API_KEY = st.secrets["BREEZE_API_KEY"]
BREEZE_API_SECRET = st.secrets["BREEZE_API_SECRET"]
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# --------------------------------
# USER INPUT
# --------------------------------
icici_session_token = st.text_input("ICICI Breeze Session Token (paste here if expired)", type="password")

STOCKS = {
    "RELIANCE": "RELIANCE",
    "TCS": "TCS", 
    "INFY": "INFY",
    "HDFCBANK": "HDFCBANK",
    "ICICIBANK": "ICICIBANK"
}

EXCHANGES = ["NSE", "BSE", "NFO"]
selected_exchange = st.selectbox("Select Exchange", options=EXCHANGES, index=0)
selected_stock = st.selectbox("Select Stock", options=list(STOCKS.keys()))
data_type = st.selectbox("Select Data Type to Display", options=["LTP", "OHLC", "Volume", "Raw JSON"])
analyze = st.button("Analyze Market")

# --------------------------------
# FETCH MARKET DATA
# --------------------------------
def generate_checksum(timestamp, payload, secret_key):
    """Generate SHA256 checksum for Breeze API authentication"""
    data = timestamp + payload + secret_key
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def fetch_market_data_icici(symbol, exchange, session_token, api_key, api_secret):
    """
    Fetch market data from ICICI Direct Breeze API using proper authentication
    """
    if not session_token:
        st.error("❌ Session token is required! Please paste it above.")
        return None

    # ✅ CORRECT API endpoint from official documentation
    url = "https://api.icicidirect.com/breezeapi/api/v1/quotes"
    
    # ✅ REQUIRED payload structure
    payload_dict = {
        "stock_code": symbol,
        "exchange_code": exchange
    }
    payload = json.dumps(payload_dict)
    
    # ✅ Generate timestamp
    timestamp = datetime.utcnow().isoformat()[:19] + '.000Z'
    
    # ✅ CRITICAL: Generate checksum - this is REQUIRED for authentication
    checksum = generate_checksum(timestamp, payload, api_secret)
    
    # ✅ CORRECT headers with all required fields
    headers = {
        "Content-Type": "application/json",
        "X-Checksum": f"token {checksum}",  # Format: "token {checksum_value}"
        "X-Timestamp": timestamp,
        "X-AppKey": api_key,
        "X-SessionToken": session_token,
        "User-Agent": "Mozilla/5.0"
    }

    try:
        # Use GET request with data payload (as per API docs)
        response = requests.get(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        
        # Check API status
        status = result.get("Status")
        if status not in [200, "200"]:
            error_msg = result.get("Error", "Unknown API error")
            st.error(f"❌ API Error: {error_msg}")
            st.json(result)  # Show raw response for debugging
            return None
            
        # Extract data from Success key
        market_data = result.get("Success")
        if not market_data:
            st.error("❌ No market data returned from API.")
            return None
            
        return market_data
        
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ HTTP Error: {e}")
        if 'response' in locals():
            st.error(f"Status Code: {response.status_code}")
            st.error(f"Response: {response.text}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to fetch data: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"❌ Failed to parse JSON response: {e}")
        if 'response' in locals():
            st.error(f"Raw response: {response.text}")
        return None

# --------------------------------
# CALL AI LLM
# --------------------------------
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
        st.error(f"❌ Failed to fetch AI insight: {e}")
        return None

# --------------------------------
# MAIN FLOW
# --------------------------------
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

        if data_type == "Raw JSON":
            st.json(market_data)
        elif data_type == "LTP":
            if isinstance(market_data, list) and len(market_data) > 0:
                ltp = market_data[0].get('ltp', 'N/A')
            else:
                ltp = market_data.get('ltp', 'N/A')
            st.metric("Last Traded Price", f"₹{ltp}")
        elif data_type == "Volume":
            if isinstance(market_data, list) and len(market_data) > 0:
                volume = market_data[0].get('total_quantity_traded', 'N/A')
            else:
                volume = market_data.get('total_quantity_traded', 'N/A')
            st.metric("Volume", f"{volume:,}" if isinstance(volume, (int, float)) else volume)
        elif data_type == "OHLC":
            if isinstance(market_data, list) and len(market_data) > 0:
                data = market_data[0]
            else:
                data = market_data
            
            ohlc = {
                'Open': data.get('open'),
                'High': data.get('high'),
                'Low': data.get('low'),
                'Close': data.get('close'),
                'Previous Close': data.get('previous_close')
            }
            st.dataframe(pd.DataFrame([ohlc]))
            st.info("ℹ️ Note: Shows current day's OHLC. For historical data, use /historicaldata endpoint.")

        # AI Analysis
        with st.spinner("🧠 AI is analyzing..."):
            insight = ask_llm(market_data)

        if insight:
            st.subheader("🤖 AI Trading Insight")
            st.markdown(insight)
