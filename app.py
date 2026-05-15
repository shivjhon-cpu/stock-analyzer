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

# --- फंक्शन 2: एडवांस्ड एआई एनालिसिस (Gemini) + SMC Sniper Entry ---
def get_ai_analysis(ticker, news_list, current_price, support, resistance, rsi, sma_20, sma_50, sma_200, vol_surge, divergence_found, poc_price, asset_type):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return "⚠️ API Key नहीं मिली! Google Cloud चेक करें।"

    div_msg = "🚨 विशेष ध्यान दें: चार्ट में 'बुलिश डायवर्जेंस' (Bullish Divergence) पाया गया है! यह एक स्ट्रॉन्ग लिक्विडिटी स्वीप और रिवर्सल सिग्नल हो सकता है।" if divergence_found else "कोई स्पष्ट डायवर्जेंस नहीं है।"
    cur_sym = "$" if asset_type == "Commodity (Gold/Silver)" else "₹"
    
    prompt = f"""
    आप एक टॉप-टियर हेज फंड मैनेजर हैं जो 'Smart Money Concepts' (SMC) का इस्तेमाल करते हैं। {ticker} का विश्लेषण करें।
    डेटा: भाव {current_price}, RSI {rsi}, सपोर्ट {support}, रेजिस्टेंस {resistance}, वॉल्यूम ब्रेकआउट {vol_surge}x.
    मूविंग एवरेज: 20-Day {sma_20}, 50-Day {sma_50}, 200-Day {sma_200}.
    स्मार्ट मनी डेटा (POC): पिछले 90 दिनों में सबसे ज्यादा ट्रेडिंग 'Point of Control' {cur_sym}{poc_price} पर हुई है।
    विशेष सूचना: {div_msg}
    खबरें: {news_list}
    
    कृपया SMC और वॉल्यूम प्रोफाइल के आधार पर हिंदी में एकदम सटीक जवाब दें:
    1. **सलाह:** (Buy 🚀 / Wait 👁️ / Avoid 🚫)
    2. **सटीक एंट्री पॉइंट (Sniper Entry):** इंस्टीट्यूशनल ऑर्डर ब्लॉक्स और POC ({cur_sym}{poc_price}) को देखते हुए बताएं कि मौजूदा भाव पर लेना सही है, या किसी डिमांड ज़ोन (पुलबैक) तक गिरने का इंतज़ार करना चाहिए? (सटीक भाव बताएं)।
    3. **टार्गेट:** टार्गेट 1, टार्गेट 2, टार्गेट 3 (चार्ट और लिक्विडिटी ग्रैब के आधार पर)।
    4. **स्टॉप लॉस:** (लिक्विडिटी स्वीप या POC के नीचे एकदम सटीक और सुरक्षित लेवल)।
    5. **कारण:** यह रणनीति क्यों चुनी गई? (POC और ऑर्डर ब्लॉक का जिक्र करें)।
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    error_log = []
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                error_log.append(f"{model_name}: {res.status_code}")
        except Exception as e:
            error_log.append(f"{model_name}: Error")
            
    return f"⚠️ AI एनालिसिस फेल हो गया। डिटेल्स: {', '.join(error_log)}"

# --- फंक्शन 3: पोर्टफोलियो एनालिसिस ---
def get_portfolio_analysis(portfolio_df):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return "⚠️ API Key नहीं मिली!"
    
    summary = portfolio_df.to_string(index=False)
    prompt = f"पोर्टफोलियो मैनेजर के रूप में 3-5% मासिक रिटर्न के लिए इस डेटा का विश्लेषण करें और हिंदी में सुझाव दें:\n{summary}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    error_log = []
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                error_log.append(f"{model_name}: {res.status_code}")
        except Exception as e:
            error_log.append(f"{model_name}: Error")
            
    return f"⚠️ पोर्टफोलियो एनालिसिस फेल हो गया। डिटेल्स: {', '.join(error_log)}"

# --- सुरक्षा ताला (PIN System) ---
st.set_page_config(page_title="Advanced SMC Analyzer", layout="wide")

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
st.title("Pro SMC & Volume Stock Analyzer 🚀")

if 'portfolio_data' not in st.session_state: st.session_state.portfolio_data = None

asset_type = st.radio("चुनें:", ("Stock (NSE/BSE)", "Commodity (Gold/Silver)"))
raw_symbol = st.text_input("सिंबल डालें (जैसे RELIANCE, TATAMOTORS):", "RELIANCE")

if st.button("Analyze Stock"):
    with st.spinner('वॉल्यूम प्रोफाइल और स्मार्ट मनी ज़ोन स्कैन हो रहे हैं...'):
        symbol = raw_symbol.upper().strip()
        if asset_type == "Stock (NSE/BSE)" and not (symbol.endswith('.NS') or symbol.endswith('.BO')): symbol += '.NS'
        
        stock = tk.Ticker(symbol)
        df = stock.history(period="1y")
        
        if df.empty: st.error("डेटा नहीं मिला।")
        else:
            # बेसिक इंडिकेटर्स
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            df['RSI'] = 100 - (100 / (1 + gain/loss))
            df['Avg_Volume_20'] = df['Volume'].rolling(window=20).mean()
            
            # --- SMC: Point of Control (POC) कैलकुलेशन ---
            recent_90 = df.tail(90).copy()
            counts, bins = np.histogram(recent_90['Close'], bins=15, weights=recent_90['Volume'])
            poc_price = round(bins[np.argmax(counts)], 2)
            
            # डायवर्जेंस चेक
            is_div, d_price, d_rsi = detect_bullish_divergence(df)
            
            # चार्ट बनाना
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            
            # Row 1: Candlesticks
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Market'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='20 EMA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='white', width=1.5), name='200 EMA'), row=1, col=1)
            
            # POC (Smart Money Line) प्लॉट करना
            fig.add_hline(y=poc_price, line_dash="dash", line_color="yellow", row=1, col=1, annotation_text="POC (Smart Money)", annotation_position="bottom right")
            
            # Row 2: RSI
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
            
            # वीकेंड गैप्स हटाना और ज़ूम
            zoom_start = df.index[-90] if len(df) > 90 else df.index[0] 
            zoom_end = df.index[-1]
            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], range=[zoom_start, zoom_end])
            
            fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, title=f"{symbol} - SMC Daily Chart")
            st.plotly_chart(fig, use_container_width=True)
            
            # AI रिपोर्ट के लिए डेटा
            res = round(recent_90['High'].max(), 2)
            sup = round(recent_90['Low'].min(), 2)
            price = round(df['Close'].iloc[-1], 2)
            rsi_val = round(df['RSI'].iloc[-1], 2)
            vol_surge = round(df['Volume'].iloc[-1] / df['Avg_Volume_20'].iloc[-1], 1) if df['Avg_Volume_20'].iloc[-1] > 0 else 1
            
            sma_20_val = round(df['SMA_20'].iloc[-1], 2)
            sma_50_val = round(df['SMA_50'].iloc[-1], 2)
            sma_200_val = round(df['SMA_200'].iloc[-1], 2) if not pd.isna(df['SMA_200'].iloc[-1]) else "N/A"
            
            st.markdown("### 🤖 Institutional SMC Insights")
            if is_div: st.warning(f"🚀 Bullish Divergence detected at Price: {round(d_price,2)} | RSI: {round(d_rsi,2)}")
            
            # जेमिनी को नया 'POC' डेटा भेजना
            ans = get_ai_analysis(symbol, [], price, sup, res, rsi_val, sma_20_val, sma_50_val, sma_200_val, vol_surge, is_div, poc_price, asset_type)
            st.success(ans)

st.divider()
st.subheader("📊 मेरा Angel One पोर्टफोलियो")
if st.button("पोर्टफोलियो लोड करें"): st.session_state.portfolio_data = fetch_my_portfolio()

if st.session_state.portfolio_data:
    my_data = st.session_state.portfolio_data
    if "error" not in my_data:
        df_p = pd.DataFrame(my_data)
        st.dataframe(df_p[['tradingsymbol', 'quantity', 'ltp', 'profitandloss']], use_container_width=True)
        if st.button("🤖 3-5% मासिक रिटर्न के लिए AI एनालिसिस"):
            with st.spinner("जेमिनी रणनीति तैयार कर रहा है..."):
                st.info(get_portfolio_analysis(df_p))
