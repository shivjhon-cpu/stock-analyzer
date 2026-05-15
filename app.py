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

# --- फंक्शन 1: बुलिश डायवर्जेंस डिटेक्शन (गणितीय फॉर्मूला) ---
def detect_bullish_divergence(df):
    try:
        # पिछले 60 दिनों का डेटा लें
        data = df.tail(60).copy()
        # लोकल मिनिमा (खाइयाँ) ढूँढें
        n = 5 # विंडो साइज
        data['min_price'] = data['Close'].iloc[argrelextrema(data['Close'].values, np.less_indicator, order=n)[0]]
        data['min_rsi'] = data['RSI'].iloc[argrelextrema(data['RSI'].values, np.less_indicator, order=n)[0]]
        
        lows = data.dropna(subset=['min_price', 'min_rsi'])
        if len(lows) >= 2:
            last_low = lows.iloc[-1]
            prev_low = lows.iloc[-2]
            
            # बुलिश डायवर्जेंस शर्त: प्राइस का लो नीचे गिरा, पर RSI का लो ऊपर बढ़ा
            if last_low['Close'] < prev_low['Close'] and last_low['RSI'] > prev_low['RSI']:
                return True, last_low['Close'], last_low['RSI']
        return False, None, None
    except:
        return False, None, None

# --- फंक्शन 2: एडवांस्ड एआई एनालिसिस (Gemini) ---
def get_ai_analysis(ticker, news_list, current_price, support, resistance, rsi, sma_20, sma_50, sma_200, vol_surge, divergence_found, asset_type):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return "⚠️ API Key नहीं मिली!"

    div_msg = "बुलिश डायवर्जेंस (Bullish Divergence) पाया गया है!" if divergence_found else "कोई स्पष्ट डायवर्जेंस नहीं है।"
    
    prompt = f"""
    आप एक प्रोफेशनल चार्ट विश्लेषक हैं। {ticker} का विश्लेषण करें।
    डेटा: भाव {current_price}, RSI {rsi}, सपोर्ट {support}, रेजिस्टेंस {resistance}, वॉल्यूम {vol_surge}x.
    विशेष सूचना: {div_msg}
    
    कृपया कैंडल्स और RSI के आधार पर हिंदी में जवाब दें:
    1. सलाह (Buy/Wait/Avoid)
    2. टार्गेट 1, टार्गेट 2, टार्गेट 3 (चार्ट के आधार पर)
    3. स्टॉप लॉस (एकदम सटीक स्तर)
    4. कारण: क्यों यह बुलिस या बेयरिश है?
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except: continue
    return "AI एनालिसिस अभी उपलब्ध नहीं है।"

# --- फंक्शन 3: पोर्टफोलियो एनालिसिस ---
def get_portfolio_analysis(portfolio_df):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return "⚠️ API Key नहीं मिली!"
    summary = portfolio_df.to_string(index=False)
    prompt = f"पोर्टफोलियो मैनेजर के रूप में 3-5% मासिक रिटर्न के लिए इस डेटा का विश्लेषण करें और हिंदी में सुझाव दें:\n{summary}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    try:
        res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except: return "पोर्टफोलियो एरर।"

# --- सुरक्षा ताला (PIN System) ---
st.set_page_config(page_title="Advanced AI Analyzer", layout="wide")

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
st.title("Advanced AI Stock & Chart Analyzer 🚀")

if 'portfolio_data' not in st.session_state: st.session_state.portfolio_data = None

asset_type = st.radio("चुनें:", ("Stock (NSE/BSE)", "Commodity (Gold/Silver)"))
raw_symbol = st.text_input("सिंबल डालें:", "VEDL")

if st.button("Analyze Stock"):
    with st.spinner('चार्ट और डायवर्जेंस स्कैन हो रहा है...'):
        symbol = raw_symbol.upper().strip()
        if asset_type == "Stock (NSE/BSE)" and not (symbol.endswith('.NS') or symbol.endswith('.BO')): symbol += '.NS'
        
        stock = tk.Ticker(symbol)
        df = stock.history(period="1y")
        
        if df.empty: st.error("डेटा नहीं मिला।")
        else:
            # इंडिकेटर्स
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            df['RSI'] = 100 - (100 / (1 + gain/loss))
            
            # डायवर्जेंस चेक
            is_div, d_price, d_rsi = detect_bullish_divergence(df)
            
            # चार्ट बनाना (Subplots)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                               vertical_spacing=0.05, row_heights=[0.7, 0.3])
            
            # Row 1: Candlesticks
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                        low=df['Low'], close=df['Close'], name='Market'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='20 EMA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='white', width=1.5), name='200 EMA'), row=1, col=1)
            
            # Row 2: RSI
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
            
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # AI रिपोर्ट
            st.markdown("### 🤖 Pro AI Insights")
            if is_div: st.warning(f"🚀 Bullish Divergence detected at Price: {round(d_price,2)} | RSI: {round(d_rsi,2)}")
            
            # बाकी डेटा
            res = round(df.tail(60)['High'].max(), 2)
            sup = round(df.tail(60)['Low'].min(), 2)
            price = round(df['Close'].iloc[-1], 2)
            rsi_val = round(df['RSI'].iloc[-1], 2)
            vol_surge = round(df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1], 1)
            
            ans = get_ai_analysis(symbol, [], price, sup, res, rsi_val, 0, 0, 0, vol_surge, is_div, asset_type)
            st.success(ans)

st.divider()
st.subheader("📊 मेरा Angel One पोर्टफोलियो")
if st.button("लोड करें"): st.session_state.portfolio_data = fetch_my_portfolio()

if st.session_state.portfolio_data:
    my_data = st.session_state.portfolio_data
    if "error" not in my_data:
        df_p = pd.DataFrame(my_data)
        st.dataframe(df_p[['tradingsymbol', 'quantity', 'ltp', 'profitandloss']], use_container_width=True)
        if st.button("🤖 AI पोर्टफोलियो एनालिसिस"):
            st.info(get_portfolio_analysis(df_p))
