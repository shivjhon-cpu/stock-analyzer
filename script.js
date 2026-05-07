/**
 * Client-side gate for casual cloud hosting. Anyone can inspect this file —
 * rotate the PIN in source before deploying; swap to server-side auth for strong security.
 * @type {string}
 */
const APP_ACCESS_PIN = "2026";

/** Session persistence: survives refresh until browser tab/session ends. */
const AUTH_SESSION_KEY = "ssa_pin_unlocked_v1";

/** Same-origin API (Flask serves UI + /api); use empty string on PythonAnywhere. */
const API_BASE = "";

const LC = typeof window !== "undefined" ? window.LightweightCharts : null;

const loginScreen = document.getElementById("loginScreen");
const appShell = document.getElementById("appShell");
const pinLoginForm = document.getElementById("pinLoginForm");
const pinInput = document.getElementById("pinInput");
const pinError = document.getElementById("pinError");

const stockSearchForm = document.getElementById("stockSearchForm");
const stockInput = document.getElementById("stockInput");
const submitButton = stockSearchForm.querySelector('button[type="submit"]');
const resultCard = document.getElementById("resultCard");
const decisionStatus = document.getElementById("decisionStatus");
const resultNote = document.getElementById("resultNote");
const chartSymbol = document.getElementById("chartSymbol");
const chartPane = document.getElementById("chartPane");
const chartContainer = document.getElementById("chartContainer");
const chartFallback = document.getElementById("chartFallback");
const chartForecastLegend = document.getElementById("chartForecastLegend");
const chartForecastLegendText = document.getElementById("chartForecastLegendText");
const forecastModelLabel = document.getElementById("forecastModelLabel");
const rsiValue = document.getElementById("rsiValue");
const emaValue = document.getElementById("emaValue");
const volumeValue = document.getElementById("volumeValue");
const predictionList = document.getElementById("predictionList");
const sma10Value = document.getElementById("sma10Value");
const sma20Value = document.getElementById("sma20Value");
const pivotValue = document.getElementById("pivotValue");
const s1Value = document.getElementById("s1Value");
const s2Value = document.getElementById("s2Value");
const s3Value = document.getElementById("s3Value");
const r1Value = document.getElementById("r1Value");
const r2Value = document.getElementById("r2Value");
const r3Value = document.getElementById("r3Value");

let chartInstance = null;
let resizeObserver = null;

const INITIAL_FALLBACK =
  "Enter a ticker and analyze to load the candlestick chart.";
const FORECAST_MODEL_LABEL = "EMA Momentum Projection";

const CANDLE_UP = "#17c964";
const CANDLE_DOWN = "#ff4d67";

function setDecisionClass(decision) {
  resultCard.classList.remove("result-buy", "result-wait", "result-avoid");
  if (decision === "STRONG BUY") {
    resultCard.classList.add("result-buy");
  } else if (decision === "STRICTLY AVOID") {
    resultCard.classList.add("result-avoid");
  } else {
    resultCard.classList.add("result-wait");
  }
}

function formatNumber(n) {
  if (n === undefined || n === null || Number.isNaN(n)) return "--";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function formatVolumeInt(v) {
  if (v === undefined || v === null) return "--";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function renderPredictions(predictions) {
  if (!predictionList) return;

  if (!Array.isArray(predictions) || !predictions.length) {
    predictionList.innerHTML =
      '<p class="prediction-empty">No prediction data available.</p>';
    return;
  }

  predictionList.innerHTML = predictions
    .map((item) => {
      const date = item?.date || "--";
      const predictedClose = formatNumber(item?.predicted_close);
      return `
        <div class="prediction-row">
          <span class="prediction-date">${date}</span>
          <span class="prediction-value">${predictedClose}</span>
        </div>
      `;
    })
    .join("");
}

function setTechnicalIndicators(data = {}) {
  if (sma10Value) sma10Value.textContent = formatNumber(data.sma_10);
  if (sma20Value) sma20Value.textContent = formatNumber(data.sma_20);
  if (pivotValue) pivotValue.textContent = formatNumber(data.pivot_point);

  const supports = data.support_levels || {};
  const resistances = data.resistance_levels || {};

  if (s1Value) s1Value.textContent = formatNumber(supports.s1);
  if (s2Value) s2Value.textContent = formatNumber(supports.s2);
  if (s3Value) s3Value.textContent = formatNumber(supports.s3);
  if (r1Value) r1Value.textContent = formatNumber(resistances.r1);
  if (r2Value) r2Value.textContent = formatNumber(resistances.r2);
  if (r3Value) r3Value.textContent = formatNumber(resistances.r3);
}

function showChartFallback(text) {
  chartFallback.textContent = text;
  chartFallback.classList.remove("is-hidden");
}

function hideChartFallback() {
  chartFallback.classList.add("is-hidden");
}

function setForecastLegendVisible(visible) {
  if (!chartForecastLegend) return;
  chartForecastLegend.hidden = !visible;
}

function disposeChart() {
  if (resizeObserver && chartPane) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (chartInstance) {
    chartInstance.remove();
    chartInstance = null;
  }
}

function candlesFromOhlcv(ohlcv) {
  if (!Array.isArray(ohlcv) || !ohlcv.length) return [];
  /** @type Map<string, { time: string, open: number, high: number, low: number, close: number }> */
  const byDay = new Map();
  for (const row of ohlcv) {
    if (!row || !row.date) continue;
    byDay.set(row.date, {
      time: row.date,
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
    });
  }
  return [...byDay.values()].sort((a, b) => a.time.localeCompare(b.time));
}

function lineFromPredictions(candles, predictions) {
  if (!Array.isArray(candles) || !candles.length) return [];
  if (!Array.isArray(predictions) || !predictions.length) return [];

  const lastCandle = candles[candles.length - 1];
  const forecastPoints = predictions
    .filter((item) => item && item.date)
    .map((item) => ({
      time: item.date,
      value: Number(item.predicted_close),
    }))
    .filter((p) => Number.isFinite(p.value));

  if (!forecastPoints.length) return [];

  // Anchor the line from the latest known close into forecasted prices.
  return [{ time: lastCandle.time, value: Number(lastCandle.close) }, ...forecastPoints];
}

function isDashboardVisible() {
  return Boolean(appShell && !appShell.hidden);
}

function revealDashboard() {
  if (loginScreen) loginScreen.hidden = true;
  if (appShell) appShell.hidden = false;
  disposeChart();
  setForecastLegendVisible(false);
  showChartFallback(INITIAL_FALLBACK);
  if (pinInput) {
    pinInput.value = "";
    pinInput.setAttribute("aria-invalid", "false");
  }
  if (pinError) pinError.hidden = true;
}

function initPinGate() {
  if (!loginScreen || !appShell || !pinLoginForm || !pinInput) return;

  if (sessionStorage.getItem(AUTH_SESSION_KEY) === "1") {
    revealDashboard();
  } else {
    loginScreen.hidden = false;
    appShell.hidden = true;
    requestAnimationFrame(() => pinInput.focus());
  }

  pinInput.addEventListener("input", () => {
    if (pinError) pinError.hidden = true;
    pinInput.setAttribute("aria-invalid", "false");
  });

  pinLoginForm.addEventListener("submit", (evt) => {
    evt.preventDefault();
    const pin = pinInput.value.trim();
    if (pin === APP_ACCESS_PIN) {
      sessionStorage.setItem(AUTH_SESSION_KEY, "1");
      revealDashboard();
      return;
    }
    pinError.hidden = false;
    pinInput.setAttribute("aria-invalid", "true");
    pinInput.select();
  });
}

function refreshChartDimensions() {
  if (!chartInstance || !chartPane || !chartContainer) return;
  const w = Math.max(1, Math.floor(chartPane.clientWidth));
  const h = Math.max(1, Math.floor(chartPane.clientHeight));
  chartInstance.applyOptions({ width: w, height: h });
}

function renderChart(ohlcv, predictions = []) {
  disposeChart();

  const candles = candlesFromOhlcv(ohlcv);
  if (!candles.length) {
    setForecastLegendVisible(false);
    showChartFallback("No OHLC rows returned — cannot render the chart.");
    return;
  }

  if (!LC || typeof LC.createChart !== "function") {
    setForecastLegendVisible(false);
    showChartFallback(
      "TradingView Lightweight Charts failed to load. Check your network/CDN.",
    );
    return;
  }

  hideChartFallback();

  const w = Math.max(1, Math.floor(chartPane.clientWidth));
  const h = Math.max(1, Math.floor(chartPane.clientHeight));

  chartInstance = LC.createChart(chartContainer, {
    width: w,
    height: h,
    layout: {
      background: { type: LC.ColorType.Solid, color: "#0a1127" },
      textColor: "#aab5d3",
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      fontSize: 12,
    },
    localization: {
      locale: "en-IN",
    },
    grid: {
      vertLines: { visible: false },
      horzLines: { visible: false },
    },
    rightPriceScale: {
      borderColor: "rgba(255,255,255,0.12)",
      scaleMargins: { top: 0.08, bottom: 0.12 },
    },
    timeScale: {
      borderColor: "rgba(255,255,255,0.12)",
      timeVisible: true,
      secondsVisible: false,
    },
    crosshair: {
      vertLine: { color: "rgba(170,181,211,0.32)" },
      horzLine: { color: "rgba(170,181,211,0.32)" },
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: true,
      horzTouchDrag: true,
      vertTouchDrag: false,
    },
    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: { time: true, price: true },
    },
  });

  const series = chartInstance.addCandlestickSeries({
    upColor: CANDLE_UP,
    downColor: CANDLE_DOWN,
    borderVisible: false,
    wickUpColor: CANDLE_UP,
    wickDownColor: CANDLE_DOWN,
  });

  series.setData(candles);

  const forecastLine = lineFromPredictions(candles, predictions);
  if (forecastLine.length > 1) {
    const lineSeries = chartInstance.addLineSeries({
      color: "#7aa2ff",
      lineWidth: 2,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
    });
    lineSeries.setData(forecastLine);
    setForecastLegendVisible(true);
  } else {
    setForecastLegendVisible(false);
  }

  chartInstance.timeScale().fitContent();

  resizeObserver = new ResizeObserver(() => {
    refreshChartDimensions();
  });
  resizeObserver.observe(chartPane);
}

initPinGate();
if (chartForecastLegendText) chartForecastLegendText.textContent = FORECAST_MODEL_LABEL;
if (forecastModelLabel) forecastModelLabel.textContent = FORECAST_MODEL_LABEL;

stockSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!isDashboardVisible()) return;

  const symbol = stockInput.value.trim().toUpperCase();
  if (!symbol) return;

  const prevLabel = submitButton.textContent;
  submitButton.disabled = true;
  submitButton.textContent = "Loading…";

  disposeChart();
  setForecastLegendVisible(false);
  showChartFallback("Loading chart…");

  try {
    const url = `${API_BASE}/api/analyze?ticker=${encodeURIComponent(symbol)}`;
    const response = await fetch(url);
    const data = await response.json().catch(() => ({}));

    if (!response.ok || !data.ok) {
      const msg = data.error || `Request failed (${response.status})`;
      setDecisionClass("WAIT & WATCH");
      decisionStatus.textContent = "ERROR";
      resultNote.textContent = msg;
      chartSymbol.textContent = symbol;
      rsiValue.textContent = "--";
      emaValue.textContent = "--";
      volumeValue.textContent = "--";
      setTechnicalIndicators({});
      renderPredictions([]);
      showChartFallback(msg);
      return;
    }

    setDecisionClass(data.decision);
    decisionStatus.textContent = data.decision;
    resultNote.textContent = data.note || "";
    chartSymbol.textContent = `${data.ticker} (1D)`;

    rsiValue.textContent = formatNumber(data.rsi_14);
    emaValue.textContent = formatNumber(data.ema_50);
    volumeValue.textContent = `${formatVolumeInt(data.latest_volume)} (10d avg ${formatVolumeInt(data.avg_volume_10)})`;
    setTechnicalIndicators(data);
    renderPredictions(data.predicted_prices_7d);
// --- 🚀 Prophet AI और Sentiment डेटा को अपडेट करना ---
if (data.prophet_targets) {
  document.getElementById('prophet1M').textContent = "₹" + data.prophet_targets.target_1M;
  document.getElementById('prophet3M').textContent = "₹" + data.prophet_targets.target_3M;
}

if (data.market_sentiment) {
  const sLabel = document.getElementById('sentimentLabel');
  sLabel.textContent = data.market_sentiment.label;
  
  // कलर कोडिंग: Positive के लिए हरा, Negative के लिए लाल, बाकी के लिए ग्रे
  if (data.market_sentiment.label.includes("POSITIVE")) {
    sLabel.style.background = "#28a745";
  } else if (data.market_sentiment.label.includes("NEGATIVE")) {
    sLabel.style.background = "#dc3545";
  } else {
    sLabel.style.background = "#6c757d";
  }
}
// ---------------------------------------------------
// --- 🚀 असली AI डेटा यहाँ भरा जाएगा ---
if (data.prophet_targets) {
  document.getElementById('prophet1M').textContent = "₹" + data.prophet_targets.target_1M;
  document.getElementById('prophet3M').textContent = "₹" + data.prophet_targets.target_3M;
}

if (data.market_sentiment) {
  const sLabel = document.getElementById('sentimentLabel');
  if(sLabel) {
      sLabel.textContent = data.market_sentiment.label;
      // पॉजिटिव मूड के लिए हरा, नेगेटिव के लिए लाल
      sLabel.style.background = data.market_sentiment.label.includes("POSITIVE") ? "#28a745" : "#dc3545";
  }
}
    renderChart(data.ohlcv, data.predicted_prices_7d);
  } catch (err) {
    setDecisionClass("WAIT & WATCH");
    decisionStatus.textContent = "ERROR";
    resultNote.textContent =
      "Could not reach the backend. Is the Flask server running on port 5000?";
    chartSymbol.textContent = symbol;
    rsiValue.textContent = "--";
    emaValue.textContent = "--";
    volumeValue.textContent = "--";
    document.getElementById('prophet1M').textContent = "--";
    document.getElementById('prophet3M').textContent = "--";
    const sLabel = document.getElementById('sentimentLabel');
    if(sLabel) {
        sLabel.textContent = "ERROR";
        sLabel.style.background = "#6c757d";
    }
    setTechnicalIndicators({});
    renderPredictions([]);
    showChartFallback(
      "Could not load data. Ensure the Flask API is running and try again.",
    );
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = prevLabel;
  }
});
