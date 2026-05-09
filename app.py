import streamlit as st
import yfinance as tk
import requests
import os
import pandas as pd

def get_ai_analysis(ticker, news_list, current_price, support, resistance):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ API Key नहीं मिली! कृपया Google Cloud में GEMINI_API_KEY चेक करें।"

    prompt = f"""
    आप एक टॉप लेवल के वित्तीय विशेषज्ञ हैं। आपको {ticker} स्टॉक का एनालिसिस हिंदी में करना है।
    वर्तमान कीमत (Current Price): ₹{current_price}
    सपोर्ट (Support): ₹{support}
    रेजिस्टेंस (Resistance): ₹{resistance}
    हाल की खबरें (News): {news_list}
    
    कृपया अपना जवाब बिल्कुल इसी सटीक फॉर्मेट में दें:
    
    1. **सलाह (Recommendation):** (केवल इनमें से एक चुनें: "Strong Buy 🚀", "Wait and Watch 👁️", या "Strictly Avoid 🚫")
    2. **प्राइस टार्गेट (Price Predictions):**
       - 7 दिन का टार्गेट (7-Day Target): ₹...
       - 1 महीने का टार्गेट (1-Month Target): ₹...
       - 3 महीने का टार्गेट (3-Month Target): ₹...
    3. **कारण और न्यूज़ एनालिसिस (Reason & News Impact):** (2-3 लाइनों में बताएं कि आपने यह सलाह और टार्गेट क्यों दिए हैं)।
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    # ये रहे गूगल के बिल्कुल नए और एक्टिव मॉडल्स!
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.5-pro"
    ]
    
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

st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")
st.title("Smart Stock Analyzer 🚀")

raw_symbol = st.text_input("स्टॉक का नाम डालें (जैसे RELIANCE, VEDL, TATAMOTORS):", "VEDL")

if st.button("Analyze"):
    with st.spinner('मार्केट डेटा और AI प्रिडिक्शन लोड हो रहे हैं... कृपया प्रतीक्षा करें ⏳'):
        
        symbol = raw_symbol.upper().strip()
        if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
            symbol = symbol + '.NS'
            
        stock = tk.Ticker(symbol)
        df = stock.history(period="6mo")
        
        if df.empty:
            st.error(f"'{symbol}' का डेटा नहीं मिला। कृपया स्पेलिंग चेक करें।")
        else:
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            
            recent_df = df.tail(60) 
            resistance = round(recent_df['High'].max(), 2)
            support = round(recent_df['Low'].min(), 2)
            current_price = round(df['Close'].iloc[-1], 2)
            current_volume = df['Volume'].iloc[-1]
            
            st.markdown("### 📊 Technical Levels")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"₹{current_price}")
            col2.metric("Support (3M)", f"₹{support}")
            col3.metric("Resistance (3M)", f"₹{resistance}")
            col4.metric("Today's Volume", f"{current_volume:,}")

            st.markdown("### 📈 Price Trend & Moving Averages (Last 3 Months)")
            chart_data = df[['Close', 'SMA_20', 'SMA_50']].tail(90) 
            st.line_chart(chart_data)
            
            news = stock.news
            news_titles = []
            news_items = []
            
            if news:
                for n in news[:5]:
                    if isinstance(n, dict):
                        t = n.get('title', n.get('content', 'मार्केट अपडेट उपलब्ध'))
                        l = n.get('link', '#')
                        if t and t != 'Title Not Available':
                            news_titles.append(t)
                            news_items.append({"title": t, "link": l})
            
            if not news_titles:
                news_titles = ["इस स्टॉक की कोई खास खबर अभी नहीं है, टेक्निकल चार्ट्स के आधार पर एनालिसिस करें।"]
            
            st.markdown("### 🤖 AI Stock Predictions (Buy/Hold/Sell)")
            analysis = get_ai_analysis(symbol, news_titles, current_price, support, resistance)
            st.success(analysis)
            
            st.markdown("### 📰 Recent News Links")
            if news_items:
                for item in news_items:
                    st.write(f"- [{item['title']}]({item['link']})")
            else:
                st.write("कोई लिंक उपलब्ध नहीं है।")
