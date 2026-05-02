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
const rsiValue = document.getElementById("rsiValue");
const emaValue = document.getElementById("emaValue");
const volumeValue = document.getElementById("volumeValue");

let chartInstance = null;
let resizeObserver = null;

const INITIAL_FALLBACK =
  "Enter a ticker and analyze to load the candlestick chart.";

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

function showChartFallback(text) {
  chartFallback.textContent = text;
  chartFallback.classList.remove("is-hidden");
}

function hideChartFallback() {
  chartFallback.classList.add("is-hidden");
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

function isDashboardVisible() {
  return Boolean(appShell && !appShell.hidden);
}

function revealDashboard() {
  if (loginScreen) loginScreen.hidden = true;
  if (appShell) appShell.hidden = false;
  disposeChart();
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

function renderChart(ohlcv) {
  disposeChart();

  const candles = candlesFromOhlcv(ohlcv);
  if (!candles.length) {
    showChartFallback("No OHLC rows returned — cannot render the chart.");
    return;
  }

  if (!LC || typeof LC.createChart !== "function") {
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
  chartInstance.timeScale().fitContent();

  resizeObserver = new ResizeObserver(() => {
    refreshChartDimensions();
  });
  resizeObserver.observe(chartPane);
}

initPinGate();

stockSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!isDashboardVisible()) return;

  const symbol = stockInput.value.trim().toUpperCase();
  if (!symbol) return;

  const prevLabel = submitButton.textContent;
  submitButton.disabled = true;
  submitButton.textContent = "Loading…";

  disposeChart();
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

    renderChart(data.ohlcv);
  } catch (err) {
    setDecisionClass("WAIT & WATCH");
    decisionStatus.textContent = "ERROR";
    resultNote.textContent =
      "Could not reach the backend. Is the Flask server running on port 5000?";
    chartSymbol.textContent = symbol;
    rsiValue.textContent = "--";
    emaValue.textContent = "--";
    volumeValue.textContent = "--";
    showChartFallback(
      "Could not load data. Ensure the Flask API is running and try again.",
    );
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = prevLabel;
  }
});
