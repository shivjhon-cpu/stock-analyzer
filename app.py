import streamlit as st
import yfinance as tk
import google.generativeai as genai
import os

# Gemini AI सेटअप
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def get_ai_analysis(ticker, news_list):
    prompt = f"Analyze the following news for {ticker} and tell if the sentiment is Positive, Negative or Neutral. Give a brief summary in Hindi.\nNews: {news_list}"
    response = model.generate_content(prompt)
    return response.text

st.title("Smart Stock Analyzer 🚀")
symbol = st.text_input("स्टॉक का सिंबल डालें (e.g. RELIANCE.NS):", "VEDL.NS")

if st.button("Analyze"):
    # स्टॉक डेटा
    stock = tk.Ticker(symbol)
    df = stock.history(period="1mo")
    st.line_chart(df['Close'])
    
    # खबरें और AI एनालिसिस
    st.subheader("Latest News & AI Insights 📰")
    news = stock.news
    if news:
        try:
            news_titles = [n.get('title', 'Title Not Available') for n in news[:5] if isinstance(n, dict)]
        except Exception as e:
            news_titles = ["इस स्टॉक की ताज़ा खबर अभी उपलब्ध नहीं है।"]
        analysis = get_ai_analysis(symbol, news_titles)
        st.write(analysis)
        for n in news[:5]:
            st.write(f"- {n['title']} ([Link]({n['link']}))")
    else:
        st.write("फिलहाल कोई ताज़ा खबर नहीं मिली।")
