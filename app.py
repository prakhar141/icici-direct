import streamlit as st
import requests
import json
from datetime import datetime
from breeze_connect import BreezeConnect

# -------------------------------
# CONFIG
# -------------------------------
OPENROUTER_MODEL = "moonshotai/kimi-k2:free"

# -------------------------------
# STREAMLIT UI
# -------------------------------
st.set_page_config(page_title="AI Trading Assistant", layout="wide")
st.title("📈 AI Trading Assistant (Breeze + LLM)")

symbol = st.text_input("Stock Symbol", "RELIANCE")
exchange = st.selectbox("Exchange", ["NSE", "BSE"])
interval = st.selectbox("OHLC Interval", ["1minute", "5minute", "15minute"])

analyze = st.button("Analyze Market")

# -------------------------------
# BREEZE CONNECTION
# -------------------------------
@st.cache_resource
def init_breeze():
    breeze = BreezeConnect(
        api_key=st.secrets["BREEZE_API_KEY"]
    )
    breeze.generate_session(
        api_secret=st.secrets["BREEZE_API_SECRET"],
        session_token=st.secrets["BREEZE_SESSION_TOKEN"]
    )
    return breeze

breeze = init_breeze()

# -------------------------------
# DATA FETCHING
# -------------------------------
def fetch_market_data():
    ltp = breeze.get_quotes(
        stock_code=symbol,
        exchange_code=exchange,
        product_type="cash"
    )

    ohlc = breeze.get_historical_data(
        interval=interval,
        from_date=datetime.now().strftime("%Y-%m-%d"),
        to_date=datetime.now().strftime("%Y-%m-%d"),
        stock_code=symbol,
        exchange_code=exchange,
        product_type="cash"
    )

    orders = breeze.get_order_list()
    positions = breeze.get_positions()

    return {
        "ltp": ltp,
        "ohlc": ohlc,
        "orders": orders,
        "positions": positions
    }

# -------------------------------
# LLM CALL (OPENROUTER)
# -------------------------------
def ask_llm(market_data):
    prompt = f"""
You are an expert trading analyst.

Market Data:
{json.dumps(market_data, indent=2)}

Analyze:
1. Short-term trend
2. Momentum
3. Support & Resistance (if visible)
4. Risk level
5. Clear Buy / Sell / Hold suggestion

Be concise and practical.
"""

    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a professional stock trading assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    return response.json()["choices"][0]["message"]["content"]

# -------------------------------
# MAIN LOGIC
# -------------------------------
if analyze:
    with st.spinner("Fetching live market data..."):
        market_data = fetch_market_data()

    st.subheader("📊 Raw Market Data")
    st.json(market_data)

    with st.spinner("Analyzing with AI..."):
        insight = ask_llm(market_data)

    st.subheader("🤖 AI Trading Insight")
    st.markdown(insight)

