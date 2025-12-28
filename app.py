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
analyze = st.button("Analyze Market")

# --------------------------------
# DATA FETCH
# --------------------------------
def fetch_market_data(symbol):
    """
    Fetch daily OHLC and latest price (LTP) from Alpha Vantage.
    Free API key supported.
    """
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={ALPHAVANTAGE_API_KEY}&outputsize=compact"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException:
        st.error("❌ Failed to fetch data from Alpha Vantage.")
        return None

    if "Time Series (Daily)" not in data:
        st.error("❌ Alpha Vantage error or invalid symbol. Free accounts only allow daily data.")
        return None

    # Get latest price (LTP)
    try:
        latest_date = max(data["Time Series (Daily)"].keys())
        latest_data = data["Time Series (Daily)"][latest_date]
        ltp = float(latest_data["4. close"])
    except Exception:
        ltp = None

    return {
        "ltp": ltp,
        "ohlc": data
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

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException:
        st.error("❌ Failed to fetch AI insight. Check your API key or network.")
        return None

# --------------------------------
# MAIN FLOW
# --------------------------------
if analyze:
    with st.spinner("📡 Fetching daily market data..."):
        market_data = fetch_market_data(symbol)
    
    if market_data:
        st.subheader("📊 Market Data")
        st.json(market_data)

        with st.spinner("🧠 AI is analyzing..."):
            insight = ask_llm(market_data)

        if insight:
            st.subheader("🤖 AI Trading Insight")
            st.markdown(insight)
