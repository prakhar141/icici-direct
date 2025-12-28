import streamlit as st
import requests
import json
import pandas as pd

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
ICICI_SESSION = st.secrets["ICICI_SESSION_TOKEN"]
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# --------------------------------
# STOCK SELECTION
# --------------------------------
# Expand this list as needed
STOCKS = {
    "RELIANCE": "RELIANCE",
    "TCS": "TCS",
    "INFY": "INFY",
    "HDFCBANK": "HDFCBANK",
    "ICICIBANK": "ICICIBANK"
}

selected_stock = st.selectbox("Select Stock", options=list(STOCKS.keys()))
data_type = st.selectbox("Select Data Type to Display", options=["LTP", "OHLC", "Volume", "Raw JSON"])

analyze = st.button("Analyze Market")

# --------------------------------
# FETCH MARKET DATA
# --------------------------------
def fetch_market_data_icici(symbol, session_token, api_key, api_secret):
    """
    Fetch market data from ICICI Direct Breeze API using API key/secret + session token
    """
    url = f"https://breezeapi.icicidirect.com/api/v1/market/quote?scriptCode={symbol}"
    headers = {
        "X-SessionToken": session_token,
        "X-APIKey": api_key,
        "X-APISecret": api_secret
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException:
        st.error("❌ Failed to fetch data from ICICI Direct Breeze API.")
        return None

    if "data" not in data:
        st.error(data.get("message") or "❌ Invalid symbol or credentials.")
        return None

    return data["data"]

# --------------------------------
# PREPARE DATAFRAME
# --------------------------------
def prepare_chart_data_icici(ohlc_data):
    """
    Converts ICICI OHLC list to DataFrame
    """
    if not ohlc_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(ohlc_data)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    df = df.set_index('date')
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
    except requests.exceptions.RequestException:
        st.error("❌ Failed to fetch AI insight.")
        return None

# --------------------------------
# MAIN FLOW
# --------------------------------
if analyze:
    with st.spinner("📡 Fetching market data..."):
        market_data = fetch_market_data_icici(
            STOCKS[selected_stock],
            ICICI_SESSION,
            BREEZE_API_KEY,
            BREEZE_API_SECRET
        )

    if market_data:
        st.subheader(f"📊 Market Data for {selected_stock}")

        if data_type == "Raw JSON":
            st.json(market_data)
        elif data_type == "LTP":
            st.metric("Last Traded Price", market_data.get("ltp"))
        elif data_type == "Volume":
            st.metric("Volume", market_data.get("volume"))
        elif data_type == "OHLC":
            df = prepare_chart_data_icici(market_data.get("ohlcHistory", []))
            if not df.empty:
                st.line_chart(df[["open","high","low","close"]].tail(30))
            else:
                st.info("No OHLC data available for this stock.")

        # AI Analysis
        with st.spinner("🧠 AI is analyzing..."):
            insight = ask_llm(market_data)

        if insight:
            st.subheader("🤖 AI Trading Insight")
            st.markdown(insight)
