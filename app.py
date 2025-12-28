import streamlit as st
import requests
import json
from datetime import datetime

# --------------------------------
# CONFIG
# --------------------------------
OPENROUTER_MODEL = "moonshotai/kimi-k2:free"
ALPHAVANTAGE_API_KEY = st.secrets["ALPHAVANTAGE_API_KEY"]

st.set_page_config(page_title="AI Trading Assistant", layout="wide")
st.title("📈 AI Trading Assistant")

# --------------------------------
# USER QUERY
# --------------------------------
symbol = st.text_input("Stock Symbol", "RELIANCE")
interval = st.selectbox("OHLC Interval", ["1min", "5min", "15min", "30min", "60min"])

analyze = st.button("Analyze Market")

# --------------------------------
# DATA FETCH
# --------------------------------
def fetch_market_data(symbol, interval):
    # Fetch intraday OHLC
    ohlc_url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={interval}&apikey={ALPHAVANTAGE_API_KEY}&outputsize=compact"
    ohlc_response = requests.get(ohlc_url)
    ohlc_response.raise_for_status()
    ohlc_data = ohlc_response.json()
    
    # Get latest price (LTP)
    try:
        time_series_key = f"Time Series ({interval})"
        latest_timestamp = max(ohlc_data[time_series_key].keys())
        latest_data = ohlc_data[time_series_key][latest_timestamp]
        ltp = float(latest_data["4. close"])
    except KeyError:
        ltp = None

    return {
        "ltp": ltp,
        "ohlc": ohlc_data
    }

# --------------------------------
# LLM CALL
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
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a professional trading assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# --------------------------------
# MAIN FLOW
# --------------------------------
if analyze:
    with st.spinner("📡 Fetching live market data..."):
        market_data = fetch_market_data(symbol, interval)

    st.subheader("📊 Market Data")
    st.json(market_data)

    with st.spinner("🧠 AI is analyzing..."):
        insight = ask_llm(market_data)

    st.subheader("🤖 AI Trading Insight")
    st.markdown(insight)
