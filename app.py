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
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# --------------------------------
# USER INPUT
# --------------------------------
# Dynamic session token input
icici_session_token = st.text_input("ICICI Breeze Session Token (paste here if expired)", type="password")

# Stock selection
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
    if not session_token:
        st.error("❌ Session token is required! Please paste it above.")
        return None

    # Format symbol with NSE exchange prefix (required by Breeze API)
    formatted_symbol = f"NSE:{symbol}"
    
    # FIXED: Removed space, corrected parameter name to 'stockCode', and using v1 endpoint
    url = f"https://breezeapi.icicidirect.com/api/v1/market/quote?stockCode={formatted_symbol}"
    
    # FIXED: Corrected header names as per Breeze API documentation
    headers = {
        "X-SessionToken": session_token,
        "X-API-Key": api_key,      # Changed from X-APIKey
        "X-API-Secret": api_secret,  # Changed from X-APISecret
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }

    try:
        # Debug info (optional, comment out if not needed)
        # st.info(f"Calling API: {url}")
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # FIXED: Check for API success status
        if data.get("Status") not in [200, "200"]:
            error_msg = data.get("Error", "Unknown API error")
            st.error(f"❌ API Error: {error_msg}")
            st.json(data)  # Show raw response for debugging
            return None
            
        # FIXED: Extract data from 'Success' key
        market_data = data.get("Success")
        if not market_data:
            st.error("❌ No market data returned from API.")
            st.json(data)  # Show raw response for debugging
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
        # FIXED: Removed trailing space in URL
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
        if 'response' in locals():
            st.error(f"Status: {response.status_code}, Response: {response.text}")
        return None
    except (KeyError, IndexError) as e:
        st.error(f"❌ Unexpected AI response format: {e}")
        if 'response' in locals():
            st.json(response.json())
        return None

# --------------------------------
# MAIN FLOW
# --------------------------------
if analyze:
    with st.spinner("📡 Fetching market data..."):
        market_data = fetch_market_data_icici(
            STOCKS[selected_stock],
            icici_session_token,
            BREEZE_API_KEY,
            BREEZE_API_SECRET
        )

    if market_data:
        st.subheader(f"📊 Market Data for {selected_stock}")

        if data_type == "Raw JSON":
            st.json(market_data)
        elif data_type == "LTP":
            st.metric("Last Traded Price", f"₹{market_data.get('ltp', 'N/A')}")
        elif data_type == "Volume":
            st.metric("Volume", f"{market_data.get('volume', 'N/A'):,}")
        elif data_type == "OHLC":
            # NOTE: The quote endpoint returns current day OHLC, not historical data
            # For historical data, you'd need to call a different endpoint
            ohlc = {
                'Open': market_data.get('open'),
                'High': market_data.get('high'),
                'Low': market_data.get('low'),
                'Close': market_data.get('close')
            }
            st.dataframe(pd.DataFrame([ohlc]))
            st.info("ℹ️ Note: This shows current day's OHLC. For historical charts, use a different API endpoint.")

        # AI Analysis
        with st.spinner("🧠 AI is analyzing..."):
            insight = ask_llm(market_data)

        if insight:
            st.subheader("🤖 AI Trading Insight")
            st.markdown(insight)
