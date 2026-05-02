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
from sklearn.ensemble import RandomForestRegressor

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


def predict_next_7_days(close: pd.Series, volume: pd.Series) -> list[float]:
    """
    Train a Random Forest on the latest 60-90 sessions using lagged close/volume
    features, then recursively forecast 7 days ahead.
    """
    recent = (
        pd.DataFrame({"Close": close.astype(float), "Volume": volume.astype(float)})
        .dropna(how="any")
        .tail(90)
        .copy()
    )
    if len(recent) < 60:
        raise ValueError("Need at least 60 sessions for Random Forest forecasting.")

    lag_days = 5
    for lag in range(1, lag_days + 1):
        recent[f"close_lag_{lag}"] = recent["Close"].shift(lag)
        recent[f"volume_lag_{lag}"] = recent["Volume"].shift(lag)

    feature_cols = [f"close_lag_{lag}" for lag in range(1, lag_days + 1)] + [
        f"volume_lag_{lag}" for lag in range(1, lag_days + 1)
    ]
    train = recent.dropna(how="any")

    model = RandomForestRegressor(
        n_estimators=400,
        max_depth=10,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train[feature_cols], train["Close"])

    close_hist = recent["Close"].tolist()
    vol_hist = recent["Volume"].tolist()

    recent_closes_20 = close_hist[-20:]
    support = float(min(recent_closes_20))
    resistance = float(max(recent_closes_20))
    range_width = max(resistance - support, support * 0.01)
    clamp_padding = 0.12 * range_width

    predictions: list[float] = []
    for _ in range(7):
        vol_baseline = float(np.median(vol_hist[-10:]))
        if len(vol_hist) >= 5:
            vol_trend = (vol_hist[-1] - vol_hist[-5]) / 4.0
            projected_volume = max(0.0, vol_hist[-1] + vol_trend)
            next_volume = (0.65 * vol_baseline) + (0.35 * projected_volume)
        else:
            next_volume = vol_baseline

        row: dict[str, float] = {}
        for lag in range(1, lag_days + 1):
            row[f"close_lag_{lag}"] = float(close_hist[-lag])
            row[f"volume_lag_{lag}"] = float(vol_hist[-lag])

        pred = float(model.predict(pd.DataFrame([row], columns=feature_cols))[0])
        pred = float(np.clip(pred, support - clamp_padding, resistance + clamp_padding))

        predictions.append(round(pred, 4))
        close_hist.append(pred)
        vol_hist.append(next_volume)

    return predictions


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
        # Enough history for 50 EMA + RSI warmup
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
    df["RSI14"] = rsi_wilder(df["Close"], 14)
    df["VolAvg10"] = df["Volume"].rolling(window=10, min_periods=10).mean()

    last = df.iloc[-1]
    close = float(last["Close"])
    vol = float(last["Volume"])
    ema50 = float(last["EMA50"])
    rsi14 = float(last["RSI14"])
    vol_avg_10 = float(last["VolAvg10"])

    if any(math.isnan(x) for x in (ema50, rsi14, vol_avg_10)):
        return jsonify(
            {
                "ok": False,
                "error": "Not enough trading days to compute all indicators (need ~50+ sessions).",
            }
        ), 422

    decision = decide(close, ema50, rsi14, vol, vol_avg_10)
    try:
        predicted_closes = predict_next_7_days(df["Close"], df["Volume"])
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 422
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

    return jsonify(
        {
            "ok": True,
            "ticker": ticker_symbol,
            "decision": decision,
            "note": decision_note(decision),
            "latest_close": round(close, 4),
            "ema_50": round(ema50, 4),
            "rsi_14": round(rsi14, 4),
            "latest_volume": int(vol),
            "avg_volume_10": int(vol_avg_10),
            "predicted_prices_7d": predicted_prices,
            "ohlcv": ohlcv,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
