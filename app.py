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
    Document-correct call to /quotes
    """
    if not session_token:
        st.error("❌ Session token required")
        return None

    # 1.  exact JSON body (no spaces) -----------------------------
    payload_dict = {
        "stock_code": symbol,
        "exchange_code": exchange,
        "product_type": "cash",
        "right": "Others",
        "strike_price": "0"
    }
    payload_str = json.dumps(payload_dict, separators=(",", ":"))   # ≡ document requirement

    # 2.  timestamp in UTC with 0 ms ------------------------------
    timestamp = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # 3.  checksum ≡ SHA256(timestamp + payload_str + secret) ----
    checksum = hashlib.sha256((timestamp + payload_str + api_secret).encode()).hexdigest()

    # 4.  headers (document pattern) ------------------------------
    headers = {
        "Content-Type": "application/json",
        "X-Checksum": f"token {checksum}",
        "X-Timestamp": timestamp,
        "X-AppKey": api_key,
        "X-SessionToken": session_token
    }

    # 5.  GET request with JSON body (document style) -------------
    url = "https://api.icicidirect.com/breezeapi/api/v1/quotes"
    try:
        resp = requests.get(url, headers=headers, data=payload_str, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("Status") == 200:
            return data.get("Success")
        else:
            st.error(f"API error: {data.get('Error')}")
            return None
    except Exception as e:
        st.error(f"Request failed: {e}")
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
