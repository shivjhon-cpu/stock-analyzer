"""
Smart Stock Analyzer — lightweight Flask API for NSE daily data via yfinance.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# --- नए इम्पोर्ट्स ---
from prophet import Prophet
from textblob import TextBlob

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def index() -> Any:
    return render_template("index.html")


def normalize_nse_ticker(raw: str) -> str:
    """Assume NSE: append .NS when user did not pass an exchange suffix."""
    t = raw.strip().upper()
    if not t:
        return t
    if t.endswith(".NS") or t.endswith(".BO"):
        return t
    return f"{t}.NS"


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    """14-period RSI using Wilder's smoothing (standard RSI)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta.clip(upper=0.0))
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def decide(
    close: float,
    ema50: float,
    rsi: float,
    volume: float,
    vol_avg_10: float,
) -> str:
    if (
        close > ema50
        and rsi > 50
        and volume > vol_avg_10
    ):
        return "STRONG BUY"
    if close < ema50 and rsi < 40:
        return "STRICTLY AVOID"
    return "WAIT & WATCH"


def decision_note(decision: str) -> str:
    return {
        "STRONG BUY": "Price above 50 EMA, RSI above 50, and volume above 10-day average.",
        "STRICTLY AVOID": "Price below 50 EMA and RSI below 40 — trend looks weak.",
        "WAIT & WATCH": "Signals are mixed or inconclusive — wait for a clearer setup.",
    }.get(decision, "")


def bar_calendar_date(ts: pd.Timestamp) -> str:
    """TradingView daily bars expect YYYY-MM-DD in the listing timezone (IST for NSE)."""
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata")
    return t.strftime("%Y-%m-%d")


def predict_next_7_days(close: pd.Series) -> list[float]:
    """
    Project 7 days using EMA momentum:
    - daily slope is (EMA5 - EMA15)
    - slope decays by 10% each projected day
    """
    close_series = close.dropna().astype(float)
    if len(close_series) < 20:
        raise ValueError("Need at least 20 sessions for EMA momentum projection.")

    ema_5 = close_series.ewm(span=5, adjust=False).mean()
    ema_15 = close_series.ewm(span=15, adjust=False).mean()
    momentum_slope = float(ema_5.iloc[-1] - ema_15.iloc[-1])

    last_close = float(close_series.iloc[-1])
    slope = momentum_slope
    predictions: list[float] = []
    for _ in range(7):
        last_close += slope
        predictions.append(round(last_close, 4))
        slope *= 0.9

    return predictions


# --- नया फंक्शन: Prophet प्रेडिक्शन (1 और 3 महीने) ---
def get_prophet_targets(df: pd.DataFrame) -> dict:
    try:
        # yfinance डेटाफ्रेम का इंडेक्स 'Date' होता है, उसे 'ds' और 'Close' को 'y' में बदलें
        prophet_df = df.reset_index()[['Date', 'Close']]
        prophet_df.columns = ['ds', 'y']
        
        # Prophet को टाइमज़ोन से दिक्कत होती है, इसलिए टाइमज़ोन हटा दें
        if pd.api.types.is_datetime64tz_dtype(prophet_df['ds']):
            prophet_df['ds'] = prophet_df['ds'].dt.tz_localize(None)

        model = Prophet(daily_seasonality=True, yearly_seasonality=True)
        model.fit(prophet_df)
        
        future = model.make_future_dataframe(periods=90)
        forecast = model.predict(future)
        
        target_1m = float(forecast['yhat'].iloc[-60]) # 90 दिन आगे गए, 60 कदम पीछे आए = 30 दिन
        target_3m = float(forecast['yhat'].iloc[-1])  # आखिरी दिन = 90 दिन
        
        return {"target_1M": round(target_1m, 2), "target_3M": round(target_3m, 2)}
    except Exception as e:
        print(f"Prophet prediction error: {e}")
        return {"target_1M": None, "target_3M": None}


# --- नया फंक्शन: मार्केट सेंटीमेंट एनालिसिस (News API के बिना) ---
def get_sentiment(ticker_obj: yf.Ticker) -> dict:
    try:
        news = ticker_obj.news
        if not news:
            return {"score": 0.0, "label": "NEUTRAL", "reason": "No recent news found."}
        
        polarity_sum = 0
        count = 0
        for article in news:
            title = article.get('title', '')
            if title:
                blob = TextBlob(title)
                polarity_sum += blob.sentiment.polarity
                count += 1
        
        if count == 0:
            return {"score": 0.0, "label": "NEUTRAL", "reason": "Could not analyze news titles."}
            
        avg_polarity = polarity_sum / count
        
        if avg_polarity > 0.05:
            label = "POSITIVE (BULLISH)"
        elif avg_polarity < -0.05:
            label = "NEGATIVE (BEARISH)"
        else:
            label = "NEUTRAL"
            
        return {"score": round(avg_polarity, 4), "label": label, "analyzed_articles": count}
    except Exception as e:
        print(f"Sentiment analysis error: {e}")
        return {"score": 0.0, "label": "ERROR", "reason": str(e)}


@app.route("/api/health", methods=["GET"])
def health() -> Any:
    return jsonify({"ok": True})


@app.route("/api/analyze", methods=["GET"])
def analyze() -> Any:
    raw = request.args.get("ticker", "").strip()
    if not raw:
        return jsonify({"ok": False, "error": "Missing ticker parameter."}), 400

    ticker_symbol = normalize_nse_ticker(raw)

    try:
        t = yf.Ticker(ticker_symbol)
        # Enough history for 50 EMA + RSI warmup + Prophet training
        hist = t.history(period="2y", interval="1d", auto_adjust=True)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to fetch data: {e!s}"}), 502

    if hist is None or hist.empty:
        return jsonify(
            {"ok": False, "error": f"No price history returned for {ticker_symbol}."}
        ), 404

    # Flatten possible MultiIndex columns from yfinance
    if isinstance(hist.columns, pd.MultiIndex):
        hist = hist.copy()
        hist.columns = hist.columns.droplevel(1)

    ohlcv_cols = ["Open", "High", "Low", "Close", "Volume"]
    if not set(ohlcv_cols).issubset(set(hist.columns)):
        return jsonify({"ok": False, "error": "Unexpected data shape from provider."}), 502

    df = hist[ohlcv_cols].copy()
    df = df.dropna(how="any")

    df["EMA50"] = ema(df["Close"], 50)
    df["SMA10"] = df["Close"].rolling(window=10, min_periods=10).mean()
    df["SMA20"] = df["Close"].rolling(window=20, min_periods=20).mean()
    df["RSI14"] = rsi_wilder(df["Close"], 14)
    df["VolAvg10"] = df["Volume"].rolling(window=10, min_periods=10).mean()

    last = df.iloc[-1]
    close = float(last["Close"])
    vol = float(last["Volume"])
    ema50 = float(last["EMA50"])
    sma10 = float(last["SMA10"])
    sma20 = float(last["SMA20"])
    rsi14 = float(last["RSI14"])
    vol_avg_10 = float(last["VolAvg10"])

    if any(math.isnan(x) for x in (ema50, sma10, sma20, rsi14, vol_avg_10)):
        return jsonify(
            {
                "ok": False,
                "error": "Not enough trading days to compute all indicators (need ~50+ sessions).",
            }
        ), 422

    decision = decide(close, ema50, rsi14, vol, vol_avg_10)
    
    try:
        predicted_closes = predict_next_7_days(df["Close"])
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 422

    # --- नए फीचर्स को कॉल करना ---
    prophet_predictions = get_prophet_targets(hist)
    sentiment_data = get_sentiment(t)

    pivot = (float(last["High"]) + float(last["Low"]) + float(last["Close"])) / 3.0
    s1 = (2.0 * pivot) - float(last["High"])
    r1 = (2.0 * pivot) - float(last["Low"])
    s2 = pivot - (float(last["High"]) - float(last["Low"]))
    r2 = pivot + (float(last["High"]) - float(last["Low"]))
    s3 = float(last["Low"]) - 2.0 * (float(last["High"]) - pivot)
    r3 = float(last["High"]) + 2.0 * (pivot - float(last["Low"]))
    next_7_dates = pd.bdate_range(
        start=pd.Timestamp(df.index[-1]) + pd.Timedelta(days=1), periods=7
    )
    predicted_prices = [
        {"date": bar_calendar_date(d), "predicted_close": p}
        for d, p in zip(next_7_dates, predicted_closes)
    ]

    ohlcv: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        ohlcv.append(
            {
                "date": bar_calendar_date(pd.Timestamp(idx)),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            }
        )

    # JSON रिस्पॉन्स में नए डेटा पॉइंट्स जोड़े गए हैं
    return jsonify(
        {
            "ok": True,
            "ticker": ticker_symbol,
            "decision": decision,
            "note": decision_note(decision),
            "latest_close": round(close, 4),
            "ema_50": round(ema50, 4),
            "sma_10": round(sma10, 4),
            "sma_20": round(sma20, 4),
            "rsi_14": round(rsi14, 4),
            "latest_volume": int(vol),
            "avg_volume_10": int(vol_avg_10),
            "pivot_point": round(pivot, 4),
            "support_levels": {
                "s1": round(s1, 4),
                "s2": round(s2, 4),
                "s3": round(s3, 4),
            },
            "resistance_levels": {
                "r1": round(r1, 4),
                "r2": round(r2, 4),
                "r3": round(r3, 4),
            },
            "predicted_prices_7d": predicted_prices,
            "prophet_targets": prophet_predictions,      # नया डेटा
            "market_sentiment": sentiment_data,          # नया डेटा
            "ohlcv": ohlcv,
        }
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)