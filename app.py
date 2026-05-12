import streamlit as st
import yfinance as tk
import requests
import os
import pandas as pd
import numpy as np
from angel_helper import fetch_my_portfolio

# --- फंक्शन 1: स्टॉक लेवल एनालिसिस (RSI, वॉल्यूम आदि के लिए) ---
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
    - RSI (14-Day): {rsi}
    - मूविंग एवरेज: 20-Day: {sma_20}, 50-Day: {sma_50}, 200-Day: {sma_200}
    - वॉल्यूम ब्रेकआउट: {vol_surge}x
    - खबरें: {news_list}
    
    FORMAT:
    1. सलाह (Strong Buy/Wait/Avoid)
    2. टार्गेट (7 दिन, 1 महीना, 3 महीना)
    3. कारण (हिंदी में)
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
        except: continue
    return "AI एनालिसिस अभी उपलब्ध नहीं है।"

# --- फंक्शन 2: पोर्टफोलियो मास्टर एनालिसिस (Diagnostic Mode) ---
def get_portfolio_analysis(portfolio_df):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return "⚠️ API Key गूगल क्लाउड से नहीं मिल रही है!"
    
    portfolio_summary = portfolio_df.to_string(index=False)
    
    prompt = f"""
    आप एक प्रोफेशनल फंड मैनेजर हैं। यह मेरा स्टॉक पोर्टफोलियो है:
    {portfolio_summary}
    
    मेरा लक्ष्य महीने में 3 से 5 प्रतिशत का रिटर्न (Monthly Return) निकालना है। 
    कृपया इस पोर्टफोलियो का गहराई से विश्लेषण करें और हिंदी में बताएं:
    1. प्रॉफिट बुकिंग
    2. स्टॉप लॉस/एग्जिट
    3. नई अपॉर्चुनिटी
    4. रिस्क अलर्ट
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # यह लाइन हमें असली बीमारी बताएगी!
            return f"⚠️ API की असली दिक्कत ({response.status_code}): {response.text}"
    except Exception as e:
        return f"सिस्टम एरर: {e}"

# --- ऐप सेटिंग्स और सेशन स्टेट ---
st.set_page_config(page_title="Pro Stock Analyzer", layout="wide")
st.title("Pro Stock & Portfolio Analyzer 🚀")

if 'portfolio_data' not in st.session_state:
    st.session_state.portfolio_data = None

# --- टॉप सेक्शन: सिंगल स्टॉक एनालिसिस ---
asset_type = st.radio("चुनें:", ("Stock (NSE/BSE)", "Commodity (Gold/Silver)"))
raw_symbol = st.text_input("सिंबल (जैसे VEDL, TATAMOTORS):", "VEDL")

if st.button("Analyze Stock"):
    with st.spinner('एनालिसिस हो रहा है...'):
        symbol = raw_symbol.upper().strip()
        if asset_type == "Stock (NSE/BSE)" and not (symbol.endswith('.NS') or symbol.endswith('.BO')):
            symbol += '.NS'
        stock = tk.Ticker(symbol)
        df = stock.history(period="1y")
        if not df.empty:
            # इंडिकेटर्स की गणना
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            price = round(df['Close'].iloc[-1], 2)
            st.metric("Current Price", f"₹{price}")
            ans = get_ai_analysis(symbol, [], price, 0, 0, 50, 0, 0, 0, 1, asset_type)
            st.success(ans)

st.divider()

# --- बॉटम सेक्शन: एंजेल वन पोर्टफोलियो ---
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
                    st.info("🎯 अग्रेसिव रणनीति (या एरर रिपोर्ट):")
                    st.markdown(advice)
        except Exception as e:
            st.error(f"Error: {e}")
