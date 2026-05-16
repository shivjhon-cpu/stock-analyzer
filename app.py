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

# --- फंक्शन 2: एडवांस्ड एआई 'पोस्ट-मॉर्टम' (SMC + Wave + Fundamentals) ---
def get_ai_analysis(ticker, price_data, fund_data, is_div, poc_price, asset_type):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key: return "⚠️ API Key नहीं मिली! Streamlit Secrets चेक करें।"

    div_msg = "🚨 विशेष: बुलिश डायवर्जेंस पाया गया है!" if is_div else "कोई स्पष्ट डायवर्जेंस नहीं है।"
    cur_sym = "$" if asset_type == "Commodity (Gold/Silver)" else "₹"
    
    prompt = f"""
    आप एक टॉप फंड मैनेजर हैं। {ticker} का इलियट वेव और SMC के आधार पर विश्लेषण करें।
    
    डेटा:
    - भाव: {price_data['current_price']} | RSI: {price_data['rsi']}
    - POC (Smart Money): {cur_sym}{poc_price}
    - फंडामेंटल्स: P/E {fund_data.get('pe')}, Debt {fund_data.get('debt')}, ROE {fund_data.get('roe')}%
    - विशेष: {div_msg}
    
    कृपया हिंदी में जवाब दें:
    1. **मैक्रो स्ट्रक्चर (Wave Analysis):** बड़ा ट्रेंड (A-B-C या 1-5) क्या है?
    2. **The Sniper Entry:** POC ({cur_sym}{poc_price}) और फंडामेंटल्स के आधार पर 'बेस्ट एंट्री' कहाँ है?
    3. **टार्गेट और स्टॉप लॉस:** अगले 3 टार्गेट।
    4. **वर्डिक्ट:** निवेश करें या इंतज़ार?
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    # 🟢 404 एरर से बचने के लिए एकदम परमानेंट हार्डकोडेड मॉडल्स
    models_to_try = ["gemini-1.5-flash-002", "gemini-1.5-flash-8b", "gemini-1.5-pro-002", "gemini-2.0-flash-exp"]
    error_log = []
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                error_log.append(f"{model_name}({res.status_code})")
        except Exception as e:
            error_log.append(f"{model_name}(Error)")
            
    return f"⚠️ AI एनालिसिस फेल। कारण: {', '.join(error_log)}."

# --- फंक्शन 3: पोर्टफोलियो एनालिसिस ---
def get_portfolio_analysis(portfolio_df):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key: return "⚠️ API Key नहीं मिली!"
    
    summary = portfolio_df.to_string(index=False)
    prompt = f"पोर्टफोलियो मैनेजर के रूप में 3-5% मासिक रिटर्न के लिए इस डेटा का विश्लेषण करें और हिंदी में सुझाव दें:\n{summary}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    # 🟢 यहाँ भी परमानेंट हार्डकोडेड मॉडल्स
    models_to_try = ["gemini-1.5-flash-002", "gemini-1.5-flash-8b", "gemini-1.5-pro-002", "gemini-2.0-flash-exp"]
    error_log = []
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                error_log.append(f"{model_name}({res.status_code})")
        except Exception as e:
            error_log.append(f"{model_name}(Error)")
            
    return f"⚠️ पोर्टफोलियो एनालिसिस फेल। डिटेल्स: {', '.join(error_log)}"

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
        
        try:
            info = stock.info
            if not info:
                st.warning("⚠️ इस शेयर का फंडामेंटल डेटा अभी उपलब्ध नहीं है, सिर्फ टेक्निकल एनालिसिस दिखाया जा रहा है।")
                info = {}
        except:
            info = {}
            st.error("⚠️ Yahoo Finance से डेटा फेच करने में दिक्कत आई।")

        if df.empty:
            st.error(f"'{symbol}' का डेटा नहीं मिला। कृपया सिंबल चेक करें।")
        else:
            # टेक्निकल कैलकुलेशन
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            df['RSI'] = 100 - (100 / (1 + gain/loss))
            
            recent_90 = df.tail(90).copy()
            counts, bins = np.histogram(recent_90['Close'], bins=15, weights=recent_90['Volume'])
            poc_price = round(bins[np.argmax(counts)], 2)
            is_div, _, _ = detect_bullish_divergence(df)
            
            fund_data = {
                'pe': info.get('forwardPE', info.get('trailingPE', 'N/A')),
                'debt': info.get('debtToEquity', 'N/A'),
                'roe': round(info.get('returnOnEquity', 0) * 100, 2) if info.get('returnOnEquity') else 'N/A',
                'eps': info.get('trailingEps', 'N/A'),
                'mcap': f"₹{info.get('marketCap', 0)/10000000:,.2f} Cr" if info.get('marketCap') else 'N/A'
            }

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

            st.markdown("---")
            st.subheader("🤖 AI Sniper Post-Mortem Report")
            price_data = {'current_price': round(df['Close'].iloc[-1], 2), 'rsi': round(df['RSI'].iloc[-1], 2)}
            
            report = get_ai_analysis(symbol, price_data, fund_data, is_div, poc_price, asset_type)
            st.success(report)

# --- पोर्टफोलियो ---
st.divider()
st.subheader("📊 मेरा Angel One पोर्टफोलियो")
if st.button("पोर्टफोलियो लोड करें"): st.session_state.portfolio_data = fetch_my_portfolio()
if 'portfolio_data' in st.session_state and st.session_state.portfolio_data:
    df_p = pd.DataFrame(st.session_state.portfolio_data)
    st.dataframe(df_p[['tradingsymbol', 'quantity', 'ltp', 'profitandloss']], use_container_width=True)
    if st.button("🤖 3-5% मासिक रिटर्न के लिए AI एनालिसिस"):
        with st.spinner("जेमिनी रणनीति तैयार कर रहा है..."):
            st.info(get_portfolio_analysis(df_p))
