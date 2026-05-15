import streamlit as st
import yfinance as tk
import requests
import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import argrelextrema
from angel_helper import fetch_my_portfolio

# --- फंक्शन 1: बुलिश डायवर्जेंस डिटेक्शन ---
def detect_bullish_divergence(df):
    try:
        data = df.tail(60).copy()
        n = 5 
        data['min_price'] = data['Close'].iloc[argrelextrema(data['Close'].values, np.less_indicator, order=n)[0]]
        data['min_rsi'] = data['RSI'].iloc[argrelextrema(data['RSI'].values, np.less_indicator, order=n)[0]]
        
        lows = data.dropna(subset=['min_price', 'min_rsi'])
        if len(lows) >= 2:
            last_low = lows.iloc[-1]
            prev_low = lows.iloc[-2]
            if last_low['Close'] < prev_low['Close'] and last_low['RSI'] > prev_low['RSI']:
                return True, last_low['Close'], last_low['RSI']
        return False, None, None
    except:
        return False, None, None

# --- फंक्शन 2: एडवांस्ड एआई 'पोस्ट-मॉर्टम' एनालिसिस (SMC + Elliott Wave + Fundamentals) ---
def get_ai_analysis(ticker, price_data, fund_data, is_div, poc_price, asset_type):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return "⚠️ API Key नहीं मिली!"

    div_msg = "🚨 अलर्ट: बुलिश डायवर्जेंस पाया गया है!" if is_div else "कोई स्पष्ट डायवर्जेंस नहीं है।"
    cur_sym = "$" if asset_type == "Commodity (Gold/Silver)" else "₹"
    
    prompt = f"""
    आप दुनिया के सबसे बेहतरीन फंडामेंटल और टेक्निकल विश्लेषक हैं। {ticker} का 'पोस्ट-मॉर्टम' विश्लेषण करें।
    
    1. टेक्निकल डेटा (SMC & Wave):
    - भाव: {price_data['current_price']} | RSI: {price_data['rsi']}
    - POC (Smart Money Zone): {cur_sym}{poc_price}
    - सूचना: {div_msg}
    
    2. फंडामेंटल डेटा (Company Health):
    - P/E Ratio: {fund_data.get('pe', 'N/A')}
    - Debt-to-Equity (कर्ज): {fund_data.get('debt', 'N/A')}
    - ROE: {fund_data.get('roe', 'N/A')}%
    - EPS: {fund_data.get('eps', 'N/A')}
    - Market Cap: {fund_data.get('mcap', 'N/A')}
    
    कृपया इन दोनों को मिलाकर हिंदी में जवाब दें:
    1. **फंडामेंटल पोस्टमार्टम:** कंपनी आर्थिक रूप से कितनी मजबूत या कमजोर है? क्या भाव महंगा है?
    2. **मैक्रो स्ट्रक्चर (Wave Analysis):** इलियट वेव के हिसाब से बड़ा ट्रेंड क्या है?
    3. **The Sniper Entry:** फंडामेंटल्स और POC ({cur_sym}{poc_price}) को मिलाकर बताएं कि 'बेस्ट एंट्री लेवल' क्या है।
    4. **टार्गेट और स्टॉप लॉस:** अगले 3 टार्गेट और एक सुरक्षित एग्जिट पॉइंट।
    5. **फाइनल वर्डिक्ट:** निवेश के लिए Buy, Sell, या Wait?
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except: continue
    return "AI एनालिसिस अभी उपलब्ध नहीं है।"

# --- सुरक्षा ताला (PIN System) ---
st.set_page_config(page_title="Pro Sniper Analyzer", layout="wide")

def check_password():
    correct_pin = os.environ.get("APP_PIN", "1234")
    if "authenticated" not in st.session_state: st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔒 ऐप सुरक्षित है")
        pin_input = st.text_input("सिक्योरिटी पिन डालें:", type="password")
        if st.button("Unlock"):
            if pin_input == correct_pin:
                st.session_state.authenticated = True
                st.rerun()
            else: st.error("गलत पिन!")
        return False
    return True

if not check_password(): st.stop()

# --- मुख्य ऐप ---
st.title("Pro Stock 'Post-Mortem' & Sniper Analyzer 🚀")

asset_type = st.radio("चुनें:", ("Stock (NSE/BSE)", "Commodity (Gold/Silver)"))
raw_symbol = st.text_input("सिंबल डालें (जैसे RELIANCE, TATAMOTORS):", "RELIANCE")

if st.button("Deep Analyze Stock"):
    with st.spinner('डेटा का पोस्टमार्टम हो रहा है...'):
        symbol = raw_symbol.upper().strip()
        if asset_type == "Stock (NSE/BSE)" and not (symbol.endswith('.NS') or symbol.endswith('.BO')): symbol += '.NS'
        
        stock = tk.Ticker(symbol)
        df = stock.history(period="1y")
        info = stock.info # फंडामेंटल डेटा यहाँ से आता है
        
        if df.empty: st.error("डेटा नहीं मिला।")
        else:
            # टेक्निकल कैलकुलेशन
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            df['RSI'] = 100 - (100 / (1 + gain/loss))
            
            # SMC & POC
            recent_90 = df.tail(90).copy()
            counts, bins = np.histogram(recent_90['Close'], bins=15, weights=recent_90['Volume'])
            poc_price = round(bins[np.argmax(counts)], 2)
            is_div, _, _ = detect_bullish_divergence(df)
            
            # फंडामेंटल डेटा तैयार करना
            fund_data = {
                'pe': info.get('forwardPE', info.get('trailingPE', 'N/A')),
                'debt': info.get('debtToEquity', 'N/A'),
                'roe': round(info.get('returnOnEquity', 0) * 100, 2) if info.get('returnOnEquity') else 'N/A',
                'eps': info.get('trailingEps', 'N/A'),
                'mcap': f"₹{info.get('marketCap', 0)/10000000:,.2f} Cr" if info.get('marketCap') else 'N/A'
            }

            # --- UI TABS ---
            tab1, tab2 = st.tabs(["📉 Advanced Chart & SMC", "📋 Fundamental Box"])

            with tab1:
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Market'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='20 EMA'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='white', width=1.5), name='200 EMA'), row=1, col=1)
                fig.add_hline(y=poc_price, line_dash="dash", line_color="yellow", row=1, col=1, annotation_text="POC (Smart Money)")
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

            with tab2:
                st.subheader(f"📊 {symbol} Fundamentals")
                col1, col2, col3 = st.columns(3)
                col1.metric("P/E Ratio", fund_data['pe'])
                col2.metric("Debt-to-Equity", fund_data['debt'])
                col3.metric("Return on Equity (ROE)", f"{fund_data['roe']}%")
                
                col4, col5 = st.columns(2)
                col4.metric("Market Cap", fund_data['mcap'])
                col5.metric("Trailing EPS", fund_data['eps'])
                
                st.info("💡 प्रो टिप: कम P/E और कम Debt वाली कंपनी को POC के पास खरीदना सबसे सुरक्षित होता है।")

            # --- AI Insights ---
            st.markdown("---")
            st.subheader("🤖 AI Sniper Post-Mortem Report")
            price_data = {'current_price': round(df['Close'].iloc[-1], 2), 'rsi': round(df['RSI'].iloc[-1], 2)}
            vol_surge = round(df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1], 1)
            
            report = get_ai_analysis(symbol, price_data, fund_data, is_div, poc_price, asset_type)
            st.success(report)

# --- पोर्टफोलियो सेक्शन ---
st.divider()
st.subheader("📊 मेरा Angel One पोर्टफोलियो")
if st.button("लोड करें"):
    st.session_state.portfolio_data = fetch_my_portfolio()
if 'portfolio_data' in st.session_state and st.session_state.portfolio_data:
    df_p = pd.DataFrame(st.session_state.portfolio_data)
    st.dataframe(df_p[['tradingsymbol', 'quantity', 'ltp', 'profitandloss']], use_container_width=True)
