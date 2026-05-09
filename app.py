import streamlit as st
import yfinance as tk
import google.generativeai as genai
import os
import pandas as pd

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash-latest')
def get_ai_analysis(ticker, news_list, current_price, support, resistance):
    # AI को दिए गए एकदम सख्त और स्पष्ट निर्देश (Prompt)
    prompt = f"""
    आप एक टॉप लेवल के वित्तीय विशेषज्ञ हैं। आपको {ticker} स्टॉक का एनालिसिस हिंदी में करना है।
    वर्तमान कीमत (Current Price): ₹{current_price}
    सपोर्ट (Support): ₹{support}
    रेजिस्टेंस (Resistance): ₹{resistance}
    हाल की खबरें (News): {news_list}
    
    कृपया अपना जवाब बिल्कुल इसी सटीक फॉर्मेट में दें:
    
    1. **सलाह (Recommendation):** (केवल और केवल इनमें से एक चुनें: "Strong Buy 🚀", "Wait and Watch 👁️", या "Strictly Avoid 🚫")
    2. **प्राइस टार्गेट (Price Predictions):**
       - 7 दिन का टार्गेट (7-Day Target): ₹...
       - 1 महीने का टार्गेट (1-Month Target): ₹...
       - 3 महीने का टार्गेट (3-Month Target): ₹...
    3. **कारण और न्यूज़ एनालिसिस (Reason & News Impact):** (2-3 लाइनों में बताएं कि आपने यह सलाह और टार्गेट क्यों दिए हैं)।
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI एनालिसिस लाने में कुछ दिक्कत आई: {e}"

st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")
st.title("Smart Stock Analyzer 🚀")
symbol = st.text_input("स्टॉक का सिंबल डालें (e.g. RELIANCE.NS, VEDL.NS):", "VEDL.NS")

if st.button("Analyze"):
    with st.spinner('मार्केट डेटा और AI प्रिडिक्शन लोड हो रहे हैं... ⏳'):
        stock = tk.Ticker(symbol)
        df = stock.history(period="6mo")
        
        if df.empty:
            st.error("स्टॉक डेटा नहीं मिला। कृपया सिंबल चेक करें।")
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
            
            # न्यूज़ निकालने का मजबूत तरीका
            news = stock.news
            news_titles = []
            news_items = []
            
            if news:
                for n in news[:5]:
                    if isinstance(n, dict):
                        # अगर title न मिले, तो content या कोई भी टेक्स्ट उठा ले
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
