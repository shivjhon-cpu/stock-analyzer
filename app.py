import streamlit as st
import yfinance as tk
import google.generativeai as genai
import os
import pandas as pd

# Gemini AI सेटअप - (Stable 'gemini-pro' मॉडल का इस्तेमाल)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

def get_ai_analysis(ticker, news_list, current_price, support, resistance):
    prompt = f"""
    Analyze the stock {ticker} in Hindi. 
    Current Price: ₹{current_price}
    Support Level: ₹{support}
    Resistance Level: ₹{resistance}
    Recent News: {news_list}
    
    Please provide the following in Hindi:
    1. सेंटीमेंट (Sentiment): Positive, Negative or Neutral.
    2. ताज़ा खबरों का सार (Brief News Summary).
    3. शॉर्ट-टर्म प्रिडिक्शन (7 Days): Based on news and technical levels.
    4. मीडियम-टर्म आउटलुक (1 to 3 Months): Overall trend analysis.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI एनालिसिस लाने में कुछ दिक्कत आई: {e}"

# ऐप का लेआउट सेट करना
st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")
st.title("Smart Stock Analyzer 🚀")
symbol = st.text_input("स्टॉक का सिंबल डालें (e.g. RELIANCE.NS):", "VEDL.NS")

if st.button("Analyze"):
    with st.spinner('मार्केट डेटा और AI इनसाइट्स लोड हो रहे हैं... कृपया प्रतीक्षा करें! ⏳'):
        # स्टॉक डेटा (6 महीने का डेटा ताकि मूविंग एवरेज सटीक निकले)
        stock = tk.Ticker(symbol)
        df = stock.history(period="6mo")
        
        if df.empty:
            st.error("स्टॉक डेटा नहीं मिला। कृपया सिंबल चेक करें (जैसे TATASTEEL.NS)।")
        else:
            # --- 1. टेक्निकल इंडिकेटर्स कैलकुलेशन ---
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            
            recent_df = df.tail(60) # पिछले 3 महीने
            resistance = round(recent_df['High'].max(), 2)
            support = round(recent_df['Low'].min(), 2)
            current_price = round(df['Close'].iloc[-1], 2)
            current_volume = df['Volume'].iloc[-1]
            
            # --- 2. टॉप मेट्रिक्स (UI में बॉक्सेस) ---
            st.markdown("### 📊 Technical Levels")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"₹{current_price}")
            col2.metric("Support (3M)", f"₹{support}")
            col3.metric("Resistance (3M)", f"₹{resistance}")
            col4.metric("Today's Volume", f"{current_volume:,}")

            # --- 3. एडवांस्ड चार्ट (Price + Moving Averages) ---
            st.markdown("### 📈 Price Trend & Moving Averages (Last 3 Months)")
            chart_data = df[['Close', 'SMA_20', 'SMA_50']].tail(90) 
            st.line_chart(chart_data)
            
            # --- 4. खबरें सुरक्षित तरीके से निकालना ---
            news = stock.news
            news_titles = []
            news_items = []
            
            if news:
                for n in news[:5]:
                    if isinstance(n, dict):
                        # अगर 'title' या 'link' न मिले तो ऐप क्रैश नहीं होगी
                        t = n.get('title', 'Title Not Available')
                        l = n.get('link', '#')
                        news_titles.append(t)
                        news_items.append({"title": t, "link": l})
            
            if not news_titles:
                news_titles = ["इस स्टॉक की ताज़ा खबर अभी उपलब्ध नहीं है।"]
            
            # --- 5. AI Analysis & Predictions ---
            st.markdown("### 🤖 AI Stock Analysis & Predictions")
            analysis = get_ai_analysis(symbol, news_titles, current_price, support, resistance)
            st.info(analysis)
            
            # --- 6. News Links Display ---
            st.markdown("### 📰 Recent News Links")
            if news_items:
                for item in news_items:
                    st.write(f"- [{item['title']}]({item['link']})")
            else:
                st.write("कोई लिंक उपलब्ध नहीं है।")
