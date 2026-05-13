import streamlit as st
import yfinance as tk
import requests
import os
import pandas as pd
import numpy as np
from angel_helper import fetch_my_portfolio

# --- फंक्शन 1: स्टॉक लेवल एनालिसिस (RSI, वॉल्यूम और चार्ट के लिए) ---
def get_ai_analysis(ticker, news_list, current_price, support, resistance, rsi, sma_20, sma_50, sma_200, vol_surge, asset_type):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ API Key नहीं मिली! कृपया Google Cloud में GEMINI_API_KEY चेक करें।"

    currency = "USD ($)" if asset_type == "Commodity" else "INR (₹)"

    prompt = f"""
    आप दुनिया के सबसे बेहतरीन वित्तीय विश्लेषक हैं। आपको {ticker} का एनालिसिस हिंदी में करना है।
    
    मार्केट डेटा ({currency}):
    - वर्तमान कीमत: {current_price}
    - सपोर्ट: {support} | रेजिस्टेंस: {resistance}
    - RSI (14-Day): {rsi} (ध्यान दें: 70+ Overbought, 30- Oversold)
    - मूविंग एवरेज: 20-Day: {sma_20}, 50-Day: {sma_50}, 200-Day: {sma_200}
    - वॉल्यूम ब्रेकआउट: {vol_surge}x
    - खबरें: {news_list}
    
    FORMAT:
    1. **सलाह (Recommendation):** (Strong Buy 🚀, Wait and Watch 👁️, या Strictly Avoid 🚫)
    2. **प्राइस टार्गेट (Price Predictions):** 7 दिन, 1 महीना, 3 महीना
    3. **कारण और न्यूज़ एनालिसिस:** (RSI, वॉल्यूम और चार्ट स्ट्रक्चर के आधार पर)
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    # यहाँ भी स्मार्ट लूप लगा दिया गया है ताकि 404 एरर न आए
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]
    last_error = ""
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                last_error = f"({response.status_code}) मॉडल {model_name} फेल।"
        except Exception as e:
            last_error = str(e)
            
    return f"⚠️ AI एनालिसिस अभी उपलब्ध नहीं है। आखिरी एरर: {last_error}"

# --- फंक्शन 2: पोर्टफोलियो मास्टर एनालिसिस (3-5% अग्रेसिव लक्ष्य) ---
def get_portfolio_analysis(portfolio_df):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return "⚠️ API Key गूगल क्लाउड से नहीं मिल रही है!"
    
    portfolio_summary = portfolio_df.to_string(index=False)
    
    prompt = f"""
    आप एक प्रोफेशनल फंड मैनेजर हैं। यह मेरा स्टॉक पोर्टफोलियो है:
    {portfolio_summary}
    
    मेरा लक्ष्य महीने में 3 से 5 प्रतिशत का रिटर्न (Monthly Return) निकालना है। 
    कृपया इस पोर्टफोलियो का गहराई से विश्लेषण करें और हिंदी में बताएं:
    1. **प्रॉफिट बुकिंग:** कौन सा शेयर अभी बेचकर तुरंत प्रॉफिट बुक करना चाहिए?
    2. **स्टॉप लॉस/एग्जिट:** किस शेयर में मोमेंटम खत्म हो गया है और निकल जाना बेहतर है?
    3. **नई अपॉर्चुनिटी:** 3-5% मंथली रिटर्न के लिए कौन से 2-3 नए शेयर या सेक्टर जोड़ने चाहिए?
    4. **रिस्क अलर्ट:** इस अग्रेसिव लक्ष्य के हिसाब से रिस्क मैनेजमेंट की सलाह।
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]
    last_error = ""
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                last_error = f"({response.status_code}) मॉडल {model_name} फेल।"
        except Exception as e:
            last_error = str(e)
            
    return f"⚠️ API की दिक्कत: कोई भी मॉडल कनेक्ट नहीं हो पाया। आखिरी एरर: {last_error}"

# --- ऐप सेटिंग्स और सेशन स्टेट ---
st.set_page_config(page_title="Pro Stock Analyzer", layout="wide")
st.title("Pro Stock & Portfolio Analyzer 🚀")

if 'portfolio_data' not in st.session_state:
    st.session_state.portfolio_data = None

# --- टॉप सेक्शन: सिंगल स्टॉक एनालिसिस (चार्ट और इंडिकेटर्स के साथ) ---
asset_type = st.radio("चुनें:", ("Stock (NSE/BSE)", "Commodity (Gold/Silver)"))
raw_symbol = st.text_input("सिंबल (जैसे VEDL, TATAMOTORS):", "VEDL")

if st.button("Analyze Stock"):
    with st.spinner('टेक्निकल डेटा और चार्ट लोड हो रहे हैं...'):
        symbol = raw_symbol.upper().strip()
        if asset_type == "Stock (NSE/BSE)" and not (symbol.endswith('.NS') or symbol.endswith('.BO')):
            symbol += '.NS'
        stock = tk.Ticker(symbol)
        df = stock.history(period="1y")
        
        if df.empty:
            st.error(f"'{symbol}' का डेटा नहीं मिला। कृपया सिंबल चेक करें।")
        else:
            # असली कैलकुलेशन (जो कल कट गई थी)
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
            sma_20_val = round(df['SMA_20'].iloc[-1], 2)
            sma_50_val = round(df['SMA_50'].iloc[-1], 2)
            sma_200_val = round(df['SMA_200'].iloc[-1], 2) if not pd.isna(df['SMA_200'].iloc[-1]) else "N/A"
            
            cur_sym = "$" if asset_type == "Commodity" else "₹"

            # चार्ट और मैट्रिक्स दिखाना
            st.markdown("### 📊 Advanced Technical Indicators")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"{cur_sym}{current_price}")
            col2.metric("RSI (14-Day)", f"{current_rsi}", "Overbought" if current_rsi > 70 else "Oversold" if current_rsi < 30 else "Neutral", delta_color="off")
            col3.metric("Volume Surge", f"{vol_surge}x", "High Volume!" if vol_surge > 1.5 else "Normal Volume")
            col4.metric("200-Day EMA", f"{cur_sym}{sma_200_val}")

            st.markdown("### 📈 Chart Structure (Support/Resistance)")
            c1, c2 = st.columns(2)
            c1.info(f"🟢 **Support (3M):** {cur_sym}{support}")
            c2.error(f"🔴 **Resistance (3M):** {cur_sym}{resistance}")
            
            chart_data = df[['Close', 'SMA_20', 'SMA_50']].tail(90) 
            st.line_chart(chart_data)
            
            # न्यूज़ निकालना
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
            
            # असली AI एनालिसिस कॉल
            st.markdown("### 🤖 Pro AI Analysis")
            analysis = get_ai_analysis(symbol, news_titles, current_price, support, resistance, current_rsi, sma_20_val, sma_50_val, sma_200_val, vol_surge, asset_type)
            st.success(analysis)

st.divider()

# --- बॉटम सेक्शन: एंजेल वन पोर्टफोलियो (सेशन के साथ सुरक्षित) ---
st.subheader("📊 मेरा Angel One पोर्टफोलियो")

if st.button("पोर्टफोलियो लोड करें"):
    with st.spinner("Angel One से डेटा ला रहे हैं..."):
        st.session_state.portfolio_data = fetch_my_portfolio()

if st.session_state.portfolio_data:
    my_data = st.session_state.portfolio_data
    if "error" in my_data:
        st.error(my_data["error"])
    else:
        try:
            df_portfolio = pd.DataFrame(my_data)
            cols_mapping = {'tradingsymbol': 'शेयर', 'quantity': 'Qty', 'ltp': 'LTP', 'profitandloss': 'P&L'}
            available_cols = [c for c in cols_mapping.keys() if c in df_portfolio.columns]
            df_display = df_portfolio[available_cols].copy().rename(columns=cols_mapping)
            df_display['P&L'] = pd.to_numeric(df_display['P&L']).round(2)

            def color_pnl(val):
                color = '#27ae60' if val > 0 else '#e74c3c'
                return f'color: {color}; font-weight: bold;'

            st.dataframe(df_display.style.map(color_pnl, subset=['P&L']), use_container_width=True, hide_index=True)
            
            total_pnl = df_display['P&L'].sum()
            st.metric("कुल लाभ/हानि", f"₹{total_pnl:,.2f}", delta=f"{total_pnl:,.2f}")
            
            # अग्रेसिव AI बटन
            if st.button("🤖 3-5% मासिक रिटर्न के लिए AI एनालिसिस"):
                with st.spinner("जेमिनी रणनीति तैयार कर रहा है..."):
                    advice = get_portfolio_analysis(df_display)
                    st.info("🎯 अग्रेसिव रणनीति:")
                    st.markdown(advice)
        except Exception as e:
            st.error(f"Error: {e}")
