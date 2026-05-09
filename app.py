import streamlit as st
import yfinance as tk
import requests
import os
import pandas as pd
import numpy as np

def get_ai_analysis(ticker, news_list, current_price, support, resistance, rsi, sma_20, sma_50, sma_200, vol_surge):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ API Key नहीं मिली! कृपया Google Cloud में GEMINI_API_KEY चेक करें।"

    # AI के लिए नया 'सुपर प्रॉम्प्ट' जिसमें सारे टेक्निकल इंडिकेटर्स शामिल हैं
    prompt = f"""
    आप दुनिया के सबसे बेहतरीन स्टॉक एनालिस्ट हैं। आपको {ticker} स्टॉक का एनालिसिस हिंदी में करना है।
    
    मार्केट डेटा:
    - वर्तमान कीमत (Current Price): ₹{current_price}
    - सपोर्ट (Support): ₹{support} | रेजिस्टेंस (Resistance): ₹{resistance}
    - RSI (14-Day): {rsi} (ध्यान दें: 70+ Overbought, 30- Oversold)
    - मूविंग एवरेज: 20-Day: ₹{sma_20}, 50-Day: ₹{sma_50}, 200-Day (लॉन्ग टर्म ट्रेंड): ₹{sma_200}
    - वॉल्यूम (Volume): आज का वॉल्यूम पिछले 20 दिनों के औसत वॉल्यूम से {vol_surge} गुना है (Volume Breakout).
    - हाल की खबरें (News): {news_list}
    
    कृपया इन सभी टेक्निकल और फंडामेंटल डेटा का इस्तेमाल करते हुए अपना जवाब बिल्कुल इसी सटीक फॉर्मेट में दें:
    
    1. **सलाह (Recommendation):** (केवल इनमें से एक चुनें: "Strong Buy 🚀", "Wait and Watch 👁️", या "Strictly Avoid 🚫")
    2. **प्राइस टार्गेट (Price Predictions):**
       - 7 दिन का टार्गेट (7-Day Target): ₹...
       - 1 महीने का टार्गेट (1-Month Target): ₹...
       - 3 महीने का टार्गेट (3-Month Target): ₹...
    3. **कारण और न्यूज़ एनालिसिस (Reason & News Impact):** (2-3 लाइनों में बताएं कि आपने RSI, वॉल्यूम और चार्ट स्ट्रक्चर के आधार पर यह सलाह क्यों दी है)।
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

st.set_page_config(page_title="Pro Stock Analyzer", layout="wide")
st.title("Pro Stock Analyzer 🚀 (with RSI & Volume)")

raw_symbol = st.text_input("स्टॉक का नाम डालें (जैसे RELIANCE, VEDL, TATAMOTORS):", "VEDL")

if st.button("Analyze"):
    with st.spinner('RSI, वॉल्यूम और चार्ट स्ट्रक्चर का गहन एनालिसिस हो रहा है... ⏳'):
        
        symbol = raw_symbol.upper().strip()
        if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
            symbol = symbol + '.NS'
            
        # 200 दिन का एवरेज निकालने के लिए हमें कम से कम 1 साल का डेटा चाहिए
        stock = tk.Ticker(symbol)
        df = stock.history(period="1y")
        
        if df.empty:
            st.error(f"'{symbol}' का डेटा नहीं मिला।")
        else:
            # --- टेक्निकल कैलकुलेशन्स (Chart Structure) ---
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            
            # --- RSI (14-Day) कैलकुलेशन ---
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # --- फंडामेंटल वॉल्यूम कैलकुलेशन ---
            df['Avg_Volume_20'] = df['Volume'].rolling(window=20).mean()
            
            # करंट वैल्यूज़
            recent_df = df.tail(60) 
            resistance = round(recent_df['High'].max(), 2)
            support = round(recent_df['Low'].min(), 2)
            current_price = round(df['Close'].iloc[-1], 2)
            current_volume = df['Volume'].iloc[-1]
            avg_vol = df['Avg_Volume_20'].iloc[-1]
            
            # वॉल्यूम सर्ज (कितने गुना बढ़ा है)
            vol_surge = round(current_volume / avg_vol, 1) if avg_vol > 0 else 1
            current_rsi = round(df['RSI'].iloc[-1], 2)
            sma_20_val = round(df['SMA_20'].iloc[-1], 2)
            sma_50_val = round(df['SMA_50'].iloc[-1], 2)
            sma_200_val = round(df['SMA_200'].iloc[-1], 2) if not pd.isna(df['SMA_200'].iloc[-1]) else "N/A"
            
            # UI अपडेट्स
            st.markdown("### 📊 Advanced Technical Indicators")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"₹{current_price}")
            col2.metric("RSI (14-Day)", f"{current_rsi}", "Overbought" if current_rsi > 70 else "Oversold" if current_rsi < 30 else "Neutral", delta_color="off")
            col3.metric("Volume Surge", f"{vol_surge}x", "High Volume!" if vol_surge > 1.5 else "Normal Volume")
            col4.metric("200-Day EMA", f"₹{sma_200_val}")

            st.markdown("### 📈 Chart Structure (Support/Resistance)")
            c1, c2 = st.columns(2)
            c1.info(f"🟢 **Support (3M):** ₹{support}")
            c2.error(f"🔴 **Resistance (3M):** ₹{resistance}")
            
            chart_data = df[['Close', 'SMA_20', 'SMA_50']].tail(90) 
            st.line_chart(chart_data)
            
            news = stock.news
            news_titles = []
            if news:
                for n in news[:5]:
                    if isinstance(n, dict):
                        t = n.get('title', n.get('content', ''))
                        if t and t != 'Title Not Available':
                            news_titles.append(t)
            if not news_titles:
                news_titles = ["कोई खास खबर नहीं।"]
            
            # AI प्रिडिक्शन
            st.markdown("### 🤖 Pro AI Analysis (Powered by RSI & Volume)")
            analysis = get_ai_analysis(symbol, news_titles, current_price, support, resistance, current_rsi, sma_20_val, sma_50_val, sma_200_val, vol_surge)
            st.success(analysis)
