import streamlit as st
import requests
import json
from datetime import datetime
from breeze_connect import BreezeConnect

# -------------------------------
# CONFIG
# -------------------------------
OPENROUTER_MODEL = "moonshotai/kimi-k2:free"

st.set_page_config(page_title="AI Trading Assistant", layout="wide")
st.title("📈 AI Trading Assistant (Breeze + LLM)")

# -------------------------------
# CREDENTIAL INPUT
# -------------------------------
with st.sidebar:
    st.header("🔐 Breeze Login")

    breeze_api_key = st.text_input(
        "Breeze API Key",
        value=st.secrets.get("BREEZE_API_KEY", ""),
        type="password"
    )

    breeze_api_secret = st.text_input(
        "Breeze API Secret",
        value=st.secrets.get("BREEZE_API_SECRET", ""),
        type="password"
    )

    session_token = st.text_input(
        "Session Token (from Breeze login)",
        type="password",
        help="Login to ICICI Breeze → Copy session token → Paste here"
    )

    connect_btn = st.button("Connect Breeze")

# -------------------------------
# INIT BREEZE
# -------------------------------
@st.cache_resource(show_spinner=False)
def init_breeze(api_key, api_secret, session_token):
    breeze = BreezeConnect(api_key=api_key)
    breeze.generate_session(
        api_secret=api_secret,
        session_token=session_token
    )
    return breeze

breeze = None
if connect_btn:
    if breeze_api_key and breeze_api_secret and session_token:
        try:
            breeze = init_breeze(
                breeze_api_key,
                breeze_api_secret,
                session_token
            )
            st.sidebar.success("✅ Breeze Connected")
        except Exception as e:
            st.sidebar.error(f"❌ Connection failed: {e}")
    else:
        st.sidebar.warning("⚠️ Fill all Breeze credentials")

# -------------------------------
# MARKET INPUT
# -------------------------------
symbol = st.text_input("Stock Symbol", "RELIANCE")
exchange = st.selectbox("Exchange", ["NSE", "BSE"])
interval = st.selectbox("OHLC Interval", ["1minute", "5minute", "15minute"])

analyze = st.button("Analyze Market")

# -------------------------------
# DATA FETCHING
# -------------------------------
def fetch_market_data(breeze):
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

# -------------------------------
# LLM CALL
# -------------------------------
def ask_llm(market_data):
    prompt = f"""
You are an expert trading analyst.

Market Data:
{json.dumps(market_data, indent=2)}

Provide:
• Trend
• Momentum
• Support / Resistance
• Risk Level
• Buy / Sell / Hold decision

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
    if not breeze:
        st.error("⚠️ Please connect Breeze first.")
    else:
        with st.spinner("Fetching market data..."):
            market_data = fetch_market_data(breeze)

        st.subheader("📊 Market Data")
        st.json(market_data)

        with st.spinner("Analyzing with AI..."):
            insight = ask_llm(market_data)

        st.subheader("🤖 AI Insight")
        st.markdown(insight)
