import streamlit as st
import requests
import json
from datetime import datetime
import pandas as pd

# --------------------------------
# CONFIG
# --------------------------------
OPENROUTER_MODEL = "moonshotai/kimi-k2:free"
ALPHAVANTAGE_API_KEY = st.secrets["ALPHAVANTAGE_API_KEY"]

st.set_page_config(page_title="AI Trading Assistant", layout="wide")
st.title("📈 AI Trading Assistant (Free API)")

# --------------------------------
# USER INPUT
# --------------------------------
symbol = st.text_input("Stock Symbol (use .NS for NSE, .BO for BSE)", "RELIANCE.NS")
analyze = st.button("Analyze Market")

# --------------------------------
# FETCH MARKET DATA
# --------------------------------
def fetch_market_data(symbol):
    """
    Fetch daily OHLC data from Alpha Vantage (free API)
    """
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={ALPHAVANTAGE_API_KEY}&outputsize=compact"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException:
        st.error("❌ Failed to fetch data from Alpha Vantage.")
        return None

    # Handle errors from API
    if "Time Series (Daily)" not in data:
        st.error(data.get("Note") or data.get("Error Message") or "❌ Invalid symbol or free endpoint limit reached.")
        return None

    # Get LTP (latest close price)
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
# PREPARE DATA FOR VISUALIZATION
# --------------------------------
def prepare_chart_data(ohlc_data):
    """
    Converts OHLC JSON to DataFrame for plotting
    """
    ts = ohlc_data.get("Time Series (Daily)", {})
    df = pd.DataFrame(ts).T  # transpose
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.astype(float)
    return df

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
        st.error("❌ Failed to fetch AI insight.")
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

        # Prepare chart
        df = prepare_chart_data(market_data["ohlc"])
        st.subheader("📈 Price Chart (Last 30 Days)")
        st.line_chart(df["4. close"].tail(30))

        # AI Analysis
        with st.spinner("🧠 AI is analyzing..."):
            insight = ask_llm(market_data)

        if insight:
            st.subheader("🤖 AI Trading Insight")
            st.markdown(insight)
