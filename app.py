import streamlit as st, requests, json, hashlib, datetime as dt
import pandas as pd

st.set_page_config(page_title="ICICI Breeze – Quotes", layout="wide")
st.title("📈 ICICI Breeze Market Data")

# ------------------------------------------------ secrets
BREEZE_API_KEY    = st.secrets["BREEZE_API_KEY"]
BREEZE_API_SECRET = st.secrets["BREEZE_API_SECRET"]

# ------------------------------------------------ inputs
SESSION_TOK = st.text_input("SessionToken (from CustomerDetails API)",
                             type="password")
stock       = st.selectbox("Stock", ["ITC", "RELIANCE", "TCS", "INFY", "HDFCBANK"])
exchange    = st.selectbox("Exchange", ["NSE", "NFO"])
go          = st.button("Get Quote")

# ------------------------------------------------ core function
def breeze_quote(symbol, exch, session, app_key, secret):
    if not session:
        st.error("❗ Enter a valid SessionToken")
        return None

    body = json.dumps({
        "stock_code": symbol,
        "exchange_code": exch,
        "product_type": "cash",
        "right": "Others",
        "strike_price": "0"
    }, separators=(',', ':'))

    ts  = dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    sig = hashlib.sha256((ts + body + secret).encode()).hexdigest()

    hdr = {
        'Content-Type'   : 'application/json',
        'X-Checksum'     : f'token {sig}',
        'X-Timestamp'    : ts,
        'X-AppKey'       : app_key,
        'X-SessionToken' : session
    }

    url = "https://api.icicidirect.com/breezeapi/api/v1/quotes"   # ← no space
    try:
        r = requests.get(url, headers=hdr, data=body, timeout=10)
        r.raise_for_status()
        js = r.json()
        if js.get("Status") == 200:
            return js.get("Success")
        st.error(js.get("Error"))
    except requests.HTTPError as e:
        st.error(f"HTTP {e.response.status_code} – {e.response.text}")
    except Exception as e:
        st.error(str(e))
    return None

# ------------------------------------------------ run
if go:
    with st.spinner("Fetching…"):
        data = breeze_quote(stock, exchange, SESSION_TOK,
                           BREEZE_API_KEY, BREEZE_API_SECRET)
    if data:
        if isinstance(data, list) and data:
            data = data[0]
        c, o, h, l, v = data.get('close'), data.get('open'), data.get('high'), \
                       data.get('low'), data.get('total_quantity_traded')
        ltp = data.get('ltp')
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("LTP", f"₹{ltp}")
        col2.metric("Open", o)
        col3.metric("High", h)
        col4.metric("Low", l)
        col5.metric("Volume", f"{v:,}" if v else "N/A")
        with st.expander("Raw JSON"):
            st.json(data)
