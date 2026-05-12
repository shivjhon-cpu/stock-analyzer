import streamlit as st
import yfinance as tk
import requests
import os
import pandas as pd
import numpy as np
from angel_helper import fetch_my_portfolio

def get_ai_analysis(ticker, news_list, current_price, support, resistance, rsi, sma_20, sma_50, sma_200, vol_surge, asset_type):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ API Key नहीं मिली! कृपया Google Cloud में GEMINI_API_KEY चेक करें।"

    currency = "USD ($)" if asset_type == "Commodity" else "INR (₹)"

    prompt = f"""
    आप दुनिया के सबसे बेहतरीन वित्तीय विश्लेषक हैं। आपको {ticker} का एनालिसिस हिंदी में करना है।
    
    मार्केट डेटा ({currency}):
    - वर्तमान कीमत (Current Price): {current_price}
    - सपोर्ट (Support): {support} | रेजिस्टेंस (Resistance): {resistance}
    - RSI (14-Day): {rsi} (ध्यान दें: 70+ Overbought, 30- Oversold)
    - मूविंग एवरेज: 20-Day: {sma_20}, 50-Day: {sma_50}, 200-Day (लॉन्ग टर्म ट्रेंड): {sma_200}
    - वॉल्यूम (Volume): आज का वॉल्यूम पिछले 20 दिनों के औसत वॉल्यूम से {vol_surge} गुना है (Volume Breakout).
    - हाल की खबरें (News): {news_list}
    
    कृपया इन सभी टेक्निकल और फंडामेंटल डेटा का इस्तेमाल करते हुए अपना जवाब बिल्कुल इसी सटीक फॉर्मेट में दें:
    
    1. **सलाह (Recommendation):** (केवल इनमें से एक चुनें: "Strong Buy 🚀", "Wait and Watch 👁️", या "Strictly Avoid 🚫")
    2. **प्राइस टार्गेट (Price Predictions in {currency}):**
       - 7 दिन का टार्गेट (7-Day Target): ...
       - 1 महीने का टार्गेट (1-Month Target): ...
       - 3 महीने का टार्गेट (3-Month Target): ...
    3. **कारण और न्यूज़ एनालिसिस (Reason & News Impact):** (2-3 लाइनों में बताएं कि आपने RSI, वॉल्यूम और चार्ट स्ट्रक्चर के आधार पर यह सलाह क्यों दी है)।
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-pro"]
    last_error = ""
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            elif response.status_code == 404:
                last_error = response.text
                continue 
            else:
                return f"API एरर ({response.status_code}) मॉडल {model_name} पर: {response.text}"
        except Exception as e:
            return f"सिस्टम एरर: {e}"

    return f"❌ कोई भी AI मॉडल कनेक्ट नहीं हो पाया। आखिरी एरर: {last_error}"

st.set_page_config(page_title="Pro Stock & Commodity Analyzer", layout="wide")
st.title("Pro Stock & Commodity Analyzer 🚀")

# --- नया: एसेट टाइप सेलेक्शन ---
asset_type = st.radio("आप क्या एनालाइज़ करना चाहते हैं?", ("Stock (NSE/BSE)", "Commodity (Gold/Silver in USD)"))

if asset_type == "Commodity (Gold/Silver in USD)":
    st.info("💡 हिंट: Gold के लिए `GC=F` और Silver के लिए `SI=F` टाइप करें।")
    raw_symbol = st.text_input("कमोडिटी सिंबल डालें:", "GC=F")
else:
    raw_symbol = st.text_input("स्टॉक का नाम डालें (जैसे RELIANCE, VEDL, TATAMOTORS):", "VEDL")

if st.button("Analyze"):
    with st.spinner('RSI, वॉल्यूम और चार्ट स्ट्रक्चर का गहन एनालिसिस हो रहा है... ⏳'):
        
        symbol = raw_symbol.upper().strip()
        
        if asset_type == "Stock (NSE/BSE)":
            if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
                symbol = symbol + '.NS'
            
        stock = tk.Ticker(symbol)
        df = stock.history(period="1y")
        
        if df.empty:
            st.error(f"'{symbol}' का डेटा नहीं मिला। कृपया सिंबल चेक करें।")
        else:
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            df['Avg_Volume_20'] = df['Volume'].rolling(window=20).mean()
            
            recent_df = df.tail(60) 
            resistance = round(recent_df['High'].max(), 2)
            support = round(recent_df['Low'].min(), 2)
            current_price = round(df['Close'].iloc[-1], 2)
            current_volume = df['Volume'].iloc[-1]
            avg_vol = df['Avg_Volume_20'].iloc[-1]
            
            vol_surge = round(current_volume / avg_vol, 1) if avg_vol > 0 else 1
            current_rsi = round(df['RSI'].iloc[-1], 2)
            current_rsi = round(df['RSI'].iloc[-1], 2)
            sma_20_val = round(df['SMA_20'].iloc[-1], 2)
            sma_50_val = round(df['SMA_50'].iloc[-1], 2)
            sma_200_val = round(df['SMA_200'].iloc[-1], 2) if not pd.isna(df['SMA_200'].iloc[-1]) else "N/A"
