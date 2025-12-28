import streamlit as st
import requests
import json
from datetime import datetime
from breeze_connect import BreezeConnect

# --------------------------------
# CONFIG
# --------------------------------
OPENROUTER_MODEL = "moonshotai/kimi-k2:free"

st.set_page_config(page_title="AI Trading Assistant", layout="wide")
st.title("📈 AI Trading Assistant")

# --------------------------------
# INIT BREEZE (AUTO)
# --------------------------------
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

try:
    breeze = init_breeze()
    st.success("✅ Connected to Breeze")
except Exception as e:
    st.error("❌ Breeze connection failed. Check session token.")
    st.stop()

# --------------------------------
# USER QUERY
# --------------------------------
symbol = st.text_input("Stock Symbol", "RELIANCE")
exchange = st.selectbox("Exchange", ["NSE", "BSE"])
interval = st.selectbox("OHLC Interval", ["1minute", "5minute", "15minute"])

analyze = st.button("Analyze Market")

# --------------------------------
# DATA FETCH
# --------------------------------
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

    return {
        "ltp": ltp,
        "ohlc": ohlc
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
        market_data = fetch_market_data()

    st.subheader("📊 Market Data")
    st.json(market_data)

    with st.spinner("🧠 AI is analyzing..."):
        insight = ask_llm(market_data)

    st.subheader("🤖 AI Trading Insight")
    st.markdown(insight)
