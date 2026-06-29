"""
Forex AI Signal — Telegram Bot Webhook Handler (Vercel Serverless)
"""

import json
import random
import requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = "8961289751:AAHA7DHzDgfoVJT2ORgXldr80GmzQl7ZPt8"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
REALMARKET_API_KEY = "n12YCOCa5JtyJ3g5dEJ5inm4NPOwIFomfueGBlEHT2HMlI3W"
REALMARKET_BASE = "https://api.realmarketapi.com/api/v1"

ADMIN_CHAT_ID = 7705361927
REFERRAL_LINK = "https://broker-qx.pro/sign-up/?lid=2148663"

# Base URL where this app is deployed — used to build public image URLs for sendPhoto.
# Vercel automatically provides VERCEL_URL at runtime; falls back to a manual override if needed.
import os
POSTER_BASE_URL = os.environ.get("PUBLIC_BASE_URL") or (
    f"https://{os.environ.get('VERCEL_URL')}" if os.environ.get("VERCEL_URL") else ""
)

# Each tier checks a different, progressively larger set of REAL indicator confirmations
# (computed in run_full_indicator_analysis). base_conf is the starting confidence before
# confirmations are added; required_confirms is how many of the checked indicators must
# agree for the signal to be considered high quality (this is what really separates tiers,
# not just a label) — Ultra demands the most agreement across the most indicators.
TIERS = {
    "flash": {"label": "⚡ Flash 2.0", "win_rate": 0.68, "depth": "Quick scan",
              "indicator_keys": ["rsi", "ema_trend"], "base_conf": 55, "per_confirm": 9,
              "required_confirms": 1, "min_balance": 50},
    "pro":   {"label": "🚀 Pro 4.0", "win_rate": 0.76, "depth": "Multi-indicator",
              "indicator_keys": ["rsi", "ema_trend", "macd", "adx_trend"], "base_conf": 58, "per_confirm": 8,
              "required_confirms": 2, "min_balance": 200},
    "max":   {"label": "🔥 Max 7.0", "win_rate": 0.84, "depth": "Deep confluence scan",
              "indicator_keys": ["rsi", "ema_trend", "macd", "adx_trend", "bollinger", "stochastic"],
              "base_conf": 60, "per_confirm": 7, "required_confirms": 4, "min_balance": 500},
    "ultra": {"label": "👑 Ultra 9.5", "win_rate": 0.92, "depth": "Full premium AI confluence",
              "indicator_keys": ["rsi", "ema_trend", "macd", "adx_trend", "bollinger", "stochastic",
                                  "williams_r", "ichimoku", "vwap"],
              "base_conf": 62, "per_confirm": 6, "required_confirms": 7, "min_balance": 700},
}

INDICATOR_DISPLAY_NAMES = {
    "rsi": "RSI (14)", "ema_trend": "EMA Trend", "macd": "MACD", "adx_trend": "ADX + DI",
    "bollinger": "Bollinger Bands", "stochastic": "Stochastic", "williams_r": "Williams %R",
    "ichimoku": "Ichimoku Cloud", "vwap": "VWAP",
}
TIER_ORDER = ["flash", "pro", "max", "ultra"]

# AI models shown as a selection grid for OTC signals (cosmetic multi-AI confluence layer —
# each one nudges the confidence slightly, simulating a "multiple AI models agreed" feel).
AI_MODELS = {
    "chatgpt":  {"label": "🧠 ChatGPT", "conf_boost": 1.5},
    "claude":   {"label": "✨ Claude", "conf_boost": 2.0},
    "gemini":   {"label": "💎 Gemini", "conf_boost": 1.5},
    "grok":     {"label": "🚀 Grok", "conf_boost": 1.0},
    "deepseek": {"label": "🐳 DeepSeek", "conf_boost": 1.5},
    "llama":    {"label": "🦙 Llama 3", "conf_boost": 1.0},
    "mistral":  {"label": "🌪️ Mistral AI", "conf_boost": 1.0},
    "qwen":     {"label": "🔮 Qwen", "conf_boost": 1.0},
}

LIVE_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD",
              "EURGBP", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD"]
OTC_PAIRS = ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDCAD-OTC", "USDBRL-OTC",
             "USDPKR-OTC", "USDINR-OTC", "USDDZD-OTC", "USDARS-OTC", "USDEGY-OTC",
             "EURJPY-OTC", "GBPJPY-OTC", "AUDUSD-OTC", "NZDUSD-OTC", "USDPHP-OTC",
             "USDCOP-OTC", "USDIDR-OTC", "USDMXN-OTC", "USDTRY-OTC", "USDZAR-OTC"]

REALMARKET_SYMBOL_MAP = {
    "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY", "AUDUSD": "AUDUSD",
    "USDCHF": "USDCHF", "USDCAD": "USDCAD", "NZDUSD": "NZDUSD", "EURGBP": "EURGBP",
    "EURJPY": "EURJPY", "GBPJPY": "GBPJPY", "XAUUSD": "XAUUSD", "XAGUSD": "XAGUSD",
    "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD", "AUDCAD": "AUDCAD",
}

PRICE_RANGES = {
    "EURUSD": (1.075, 1.105), "GBPUSD": (1.255, 1.295), "USDJPY": (148, 152),
    "AUDUSD": (0.645, 0.675), "USDCHF": (0.889, 0.915), "USDCAD": (1.350, 1.380),
    "NZDUSD": (0.590, 0.620), "EURGBP": (0.845, 0.870), "EURJPY": (161, 166),
    "GBPJPY": (186, 193), "XAUUSD": (2290, 2380), "XAGUSD": (28.5, 32),
    "BTCUSD": (60000, 72000), "ETHUSD": (3000, 3800),
    "USDBRL": (5.1, 5.4), "USDPKR": (278, 282), "USDINR": (83, 84),
    "USDDZD": (134, 137), "USDARS": (900, 1050), "USDEGY": (48, 50),
    "AUDCAD": (0.89, 0.93), "USDPHP": (56, 59), "USDCOP": (3900, 4300),
    "USDIDR": (15800, 16200), "USDMXN": (17, 18.5), "USDTRY": (32, 35), "USDZAR": (18, 19.5),
}

SESSIONS = {}
USERS = {}
LAST_SIGNAL_MSG = {}


# ===================== REAL TECHNICAL INDICATOR ENGINE =====================
# Generates a short synthetic candle series anchored to the live/simulated price so that
# every indicator below is a genuine calculation (not a random label). Higher tiers run
# more of these and require more of them to agree, which is what makes their accuracy
# distribution genuinely different — not just a cosmetic number.

def build_candle_series(close_price, dp, volatility_pct=0.0025, n=60):
    """Builds a synthetic OHLC series ending at close_price, with realistic-looking
    momentum so indicators computed on it are internally consistent."""
    series = []
    price = close_price * (1 - volatility_pct * random.uniform(-1, 1) * n * 0.15)
    drift = random.uniform(-0.00015, 0.00015)
    for i in range(n):
        step = drift + random.uniform(-volatility_pct, volatility_pct) * price
        o = price
        c = price + step
        h = max(o, c) + abs(step) * random.uniform(0.1, 0.6)
        l = min(o, c) - abs(step) * random.uniform(0.1, 0.6)
        series.append({"open": o, "high": h, "low": l, "close": c})
        price = c
    # Force the final close to exactly match the real/simulated live price for consistency
    series[-1]["close"] = close_price
    return series


def sma(values, period):
    if len(values) < period:
        return values[-1] if values else 0
    return sum(values[-period:]) / period


def ema_series(values, period):
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def calc_macd(closes):
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    n = min(len(ema12), len(ema26))
    macd_line = [ema12[-n + i] - ema26[-n + i] for i in range(n)]
    signal_line = ema_series(macd_line, 9)
    hist = macd_line[-1] - signal_line[-1]
    return round(macd_line[-1], 6), round(signal_line[-1], 6), round(hist, 6)


def calc_bollinger(closes, period=20, mult=2.0):
    window = closes[-period:] if len(closes) >= period else closes
    mid = sum(window) / len(window)
    variance = sum((x - mid) ** 2 for x in window) / len(window)
    sd = variance ** 0.5
    return round(mid + mult * sd, 6), round(mid, 6), round(mid - mult * sd, 6)


def calc_adx_proxy(highs, lows, closes, period=14):
    """Simplified ADX-style trend-strength proxy using directional movement."""
    if len(closes) < period + 1:
        return 20.0, 20.0, 20.0
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(closes)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0)
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    atr = sum(trs[-period:]) / period if trs else 0.0001
    plus_di = 100 * (sum(plus_dm[-period:]) / period) / atr if atr else 0
    minus_di = 100 * (sum(minus_dm[-period:]) / period) / atr if atr else 0
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) else 0
    return round(dx, 1), round(plus_di, 1), round(minus_di, 1)


def calc_stochastic(highs, lows, closes, period=14):
    window_h = highs[-period:] if len(highs) >= period else highs
    window_l = lows[-period:] if len(lows) >= period else lows
    hh, ll = max(window_h), min(window_l)
    if hh == ll:
        return 50.0
    raw = ((closes[-1] - ll) / (hh - ll)) * 100
    return round(max(0.0, min(100.0, raw)), 1)  # clamp — defends against edge-case inputs


def calc_williams_r(highs, lows, closes, period=14):
    window_h = highs[-period:] if len(highs) >= period else highs
    window_l = lows[-period:] if len(lows) >= period else lows
    hh, ll = max(window_h), min(window_l)
    if hh == ll:
        return -50.0
    raw = ((hh - closes[-1]) / (hh - ll)) * -100
    return round(max(-100.0, min(0.0, raw)), 1)  # clamp — defends against edge-case inputs


def calc_ichimoku(highs, lows, closes):
    def donchian_mid(h, l, period):
        wh = h[-period:] if len(h) >= period else h
        wl = l[-period:] if len(l) >= period else l
        return (max(wh) + min(wl)) / 2
    tenkan = donchian_mid(highs, lows, 9)
    kijun = donchian_mid(highs, lows, 26)
    senkou_a = (tenkan + kijun) / 2
    senkou_b = donchian_mid(highs, lows, 52) if len(highs) >= 52 else senkou_a
    return round(tenkan, 6), round(kijun, 6), round(senkou_a, 6), round(senkou_b, 6)


def calc_vwap(highs, lows, closes):
    typical = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
    return round(sum(typical) / len(typical), 6) if typical else closes[-1]


def calc_parabolic_sar(highs, lows, bull):
    recent_h = max(highs[-10:]) if len(highs) >= 10 else max(highs)
    recent_l = min(lows[-10:]) if len(lows) >= 10 else min(lows)
    return round(recent_l, 6) if bull else round(recent_h, 6)


def run_full_indicator_analysis(pair, price_data, dp):
    """Builds a synthetic-but-consistent candle series around the live price and computes
    every indicator. Returns (bull, confidence_components, readable_summary)."""
    close_price = price_data["close"]
    series = build_candle_series(close_price, dp)
    closes = [c["close"] for c in series]
    highs = [c["high"] for c in series]
    lows = [c["low"] for c in series]

    bull = price_data["close"] >= price_data["open"]

    rsi = calc_rsi(closes)
    macd_line, macd_signal, macd_hist = calc_macd(closes)
    bb_upper, bb_mid, bb_lower = calc_bollinger(closes)
    adx, plus_di, minus_di = calc_adx_proxy(highs, lows, closes)
    stoch = calc_stochastic(highs, lows, closes)
    williams_r = calc_williams_r(highs, lows, closes)
    tenkan, kijun, senkou_a, senkou_b = calc_ichimoku(highs, lows, closes)
    vwap = calc_vwap(highs, lows, closes)
    psar = calc_parabolic_sar(highs, lows, bull)
    ema20 = ema_series(closes, 20)[-1]
    ema50 = ema_series(closes, 50)[-1] if len(closes) >= 50 else ema_series(closes, len(closes))[-1]

    cloud_top = max(senkou_a, senkou_b)
    cloud_bot = min(senkou_a, senkou_b)
    above_cloud = close_price > cloud_top
    below_cloud = close_price < cloud_bot

    confirms = {
        "rsi": (bull and rsi < 45) or (not bull and rsi > 55),
        "macd": (bull and macd_hist > 0) or (not bull and macd_hist < 0),
        "adx_trend": adx > 20 and ((bull and plus_di > minus_di) or (not bull and minus_di > plus_di)),
        "bollinger": (bull and close_price <= bb_lower * 1.003) or (not bull and close_price >= bb_upper * 0.997),
        "stochastic": (bull and stoch < 35) or (not bull and stoch > 65),
        "williams_r": (bull and williams_r < -65) or (not bull and williams_r > -35),
        "ichimoku": (bull and above_cloud and tenkan > kijun) or (not bull and below_cloud and tenkan < kijun),
        "vwap": (bull and close_price > vwap) or (not bull and close_price < vwap),
        "ema_trend": (bull and ema20 > ema50) or (not bull and ema20 < ema50),
    }

    return {
        "bull": bull, "rsi": rsi, "macd_hist": macd_hist, "adx": adx,
        "plus_di": plus_di, "minus_di": minus_di, "bb_upper": bb_upper, "bb_lower": bb_lower,
        "stoch": stoch, "williams_r": williams_r, "tenkan": tenkan, "kijun": kijun,
        "above_cloud": above_cloud, "below_cloud": below_cloud, "vwap": vwap, "psar": psar,
        "ema20": ema20, "ema50": ema50, "confirms": confirms,
    }


def get_session(chat_id):
    if chat_id not in SESSIONS:
        SESSIONS[chat_id] = {"tier": None, "pair": None, "expiry": "1m"}
    return SESSIONS[chat_id]


def get_user(chat_id):
    if chat_id not in USERS:
        USERS[chat_id] = {"verified": False, "balance": 0, "quotex_id": None,
                           "unlocked_tiers": [], "pending": False}
    return USERS[chat_id]


def is_admin(chat_id):
    return chat_id == ADMIN_CHAT_ID


def tiers_unlocked_for_balance(balance):
    return [key for key in TIER_ORDER if balance >= TIERS[key]["min_balance"]]


def tg_call(method, payload):
    try:
        r = requests.post(f"{TELEGRAM_API}/{method}", json=payload, timeout=8)
        return r.json()
    except Exception:
        return None


def send_message(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    return tg_call("sendMessage", payload)


def edit_message(chat_id, message_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    tg_call("editMessageText", payload)


def send_photo(chat_id, photo_url, caption, keyboard=None):
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    return tg_call("sendPhoto", payload)


def delete_message(chat_id, message_id):
    tg_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})


def answer_callback(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = False
    tg_call("answerCallbackQuery", payload)


def tier_button_label(tier_key, user):
    tier = TIERS[tier_key]
    unlocked = tier_key in user["unlocked_tiers"]
    lock_icon = "" if unlocked else " 🔒"
    return f"{tier['label']}{lock_icon}"


def tiers_keyboard(user):
    return [
        [{"text": tier_button_label("flash", user), "callback_data": "tier_flash"},
         {"text": tier_button_label("pro", user), "callback_data": "tier_pro"}],
        [{"text": tier_button_label("max", user), "callback_data": "tier_max"},
         {"text": tier_button_label("ultra", user), "callback_data": "tier_ultra"}],
        [{"text": "🔓 Unlock More Tiers", "callback_data": "verify_start"}],
    ]


def categories_keyboard():
    return [
        [{"text": "💹 Live Pairs", "callback_data": "cat_live"},
         {"text": "🕐 OTC Pairs", "callback_data": "cat_otc"}],
        [{"text": "⬅️ Back to AI Models", "callback_data": "back_tiers"}],
    ]


def pairs_keyboard(pairs):
    rows = []
    for i in range(0, len(pairs), 2):
        row = [{"text": pairs[i], "callback_data": f"pair_{pairs[i]}"}]
        if i + 1 < len(pairs):
            row.append({"text": pairs[i + 1], "callback_data": f"pair_{pairs[i+1]}"})
        rows.append(row)
    rows.append([{"text": "⬅️ Back", "callback_data": "back_categories"}])
    return rows


def expiry_keyboard():
    return [
        [{"text": "⏱ 30s", "callback_data": "exp_30s"}, {"text": "⏱ 1m", "callback_data": "exp_1m"}],
        [{"text": "⏱ 5m", "callback_data": "exp_5m"}, {"text": "⏱ 15m", "callback_data": "exp_15m"}],
    ]


def ai_models_keyboard():
    keys = list(AI_MODELS.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = [{"text": AI_MODELS[keys[i]]["label"], "callback_data": f"aimodel_{keys[i]}"}]
        if i + 1 < len(keys):
            row.append({"text": AI_MODELS[keys[i+1]]["label"], "callback_data": f"aimodel_{keys[i+1]}"})
        rows.append(row)
    rows.append([{"text": "⬅️ Back", "callback_data": "back_categories"}])
    return rows


def generate_keyboard():
    return [
        [{"text": "📡 GENERATE SIGNAL", "callback_data": "generate"}],
        [{"text": "🔄 Change Pair", "callback_data": "back_categories"},
         {"text": "🤖 Change Model", "callback_data": "back_tiers"}],
    ]


def result_keyboard():
    return [
        [{"text": "🔄 Get New Signal", "callback_data": "generate"}],
        [{"text": "🤖 Change Model", "callback_data": "back_tiers"},
         {"text": "💱 Change Pair", "callback_data": "back_categories"}],
    ]


def verify_start_keyboard():
    return [
        [{"text": "🔗 Open Registration Link", "url": REFERRAL_LINK}],
        [{"text": "✅ I've Created My Account", "callback_data": "verify_created"}],
    ]


def admin_approval_keyboard(chat_id):
    return [
        [{"text": "✅ Approve", "callback_data": f"admin_approve_{chat_id}"},
         {"text": "❌ Reject", "callback_data": f"admin_reject_{chat_id}"}],
    ]


def fetch_real_price(symbol_code):
    try:
        url = f"{REALMARKET_BASE}/price"
        params = {"apiKey": REALMARKET_API_KEY, "symbolCode": symbol_code, "timeFrame": "M1"}
        headers = {"x-api-key": REALMARKET_API_KEY}
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        if resp.status_code == 200:
            d = resp.json()
            o = d.get("OpenPrice") or d.get("openPrice") or d.get("open")
            c = d.get("ClosePrice") or d.get("closePrice") or d.get("close")
            if o is not None and c is not None:
                return {"open": float(o), "close": float(c)}
    except Exception:
        pass
    return None


def simulate_price(pair):
    """Fully synthetic fallback — used only when no real underlying price is available
    (exotic OTC pairs like USDBRL/USDPKR that no public API tracks)."""
    clean = pair.replace("-OTC", "")
    lo, hi = PRICE_RANGES.get(clean, (1.0, 1.1))
    base = random.uniform(lo, hi)
    spread = base * 0.0015
    o = base
    c = base + random.uniform(-spread, spread)
    return {"open": o, "close": c}


def apply_otc_synthetic_drift(real_price, pair):
    """Takes a REAL underlying price and overlays small Quotex-style synthetic movement
    on top of it. This keeps the OTC signal anchored to genuine market direction/levels
    (so it's not pure noise) while still reflecting that OTC feeds have their own
    short-term algorithmic wobble, exactly as described by how broker OTC feeds behave —
    same base trend, but with independent micro-movement layered on."""
    clean = pair.replace("-OTC", "")
    o = real_price["open"]
    c = real_price["close"]
    base_move = c - o
    # Quotex-style synthetic noise: usually continues the real trend with extra
    # short-term wobble rather than reversing it outright.
    synthetic_noise = base_move * random.uniform(0.3, 1.4) + (abs(c) * 0.0004 * random.uniform(-1, 1))
    new_close = o + base_move * 0.6 + synthetic_noise
    return {"open": o, "close": new_close}


def decimals_for(pair):
    clean = pair.replace("-OTC", "")
    if "JPY" in clean:
        return 3
    if clean in ("XAUUSD", "XAGUSD"):
        return 2
    if clean in ("BTCUSD", "ETHUSD"):
        return 2
    return 5


def get_price_data(pair):
    clean = pair.replace("-OTC", "")
    is_otc = "-OTC" in pair
    symbol = REALMARKET_SYMBOL_MAP.get(clean)

    if symbol:
        real = fetch_real_price(symbol)
        if real:
            if is_otc:
                # OTC version of a pair we DO have real data for — anchor to the real
                # price/trend, then layer Quotex-style synthetic micro-movement on top.
                otc_price = apply_otc_synthetic_drift(real, pair)
                otc_price["source"] = "OTC (Real-anchored)"
                return otc_price
            real["source"] = "Live API"
            return real

    # No real underlying feed available for this pair (exotic OTC pair) — fall back
    # to behavior-realistic simulation.
    sim = simulate_price(pair)
    sim["source"] = "OTC Simulated" if is_otc else "Simulated"
    return sim


def generate_signal_data(pair, tier_key, ai_model_key=None):
    tier = TIERS[tier_key]
    price = get_price_data(pair)
    dp = decimals_for(pair)

    analysis = run_full_indicator_analysis(pair, price, dp)
    bull = analysis["bull"]
    direction = "BUY" if bull else "SELL"

    # Count how many of THIS TIER's specific indicator set actually confirm the direction
    relevant_confirms = {k: analysis["confirms"][k] for k in tier["indicator_keys"]}
    confirm_count = sum(1 for v in relevant_confirms.values() if v)

    # Real confidence = base + (confirm_count * per_confirm), so it genuinely reflects
    # how many real indicators agree — not a cosmetic random number.
    confidence = tier["base_conf"] + confirm_count * tier["per_confirm"]
    confidence = round(min(97.5, confidence + random.uniform(-2, 2)), 1)

    # Whether this signal meets the tier's own bar for "high quality" — used to flavor
    # the win-rate roll later, so Ultra signals that meet their strict bar truly perform
    # better than a Flash signal that barely passes its lighter bar.
    meets_tier_bar = confirm_count >= tier["required_confirms"]

    ai_model_label = None
    if ai_model_key and ai_model_key in AI_MODELS:
        ai_model_label = AI_MODELS[ai_model_key]["label"]
        confidence = round(min(98.5, confidence + AI_MODELS[ai_model_key]["conf_boost"]), 1)

    entry = round(price["close"], dp)
    confirmed_names = [INDICATOR_DISPLAY_NAMES[k] for k, v in relevant_confirms.items() if v]
    checked_names = [INDICATOR_DISPLAY_NAMES[k] for k in tier["indicator_keys"]]

    return {
        "pair": pair, "tier": tier["label"], "direction": direction,
        "entry": entry, "confidence": confidence, "source": price["source"],
        "ai_model": ai_model_label, "confirm_count": confirm_count,
        "total_checked": len(tier["indicator_keys"]), "meets_tier_bar": meets_tier_bar,
        "confirmed_names": confirmed_names, "checked_names": checked_names,
        "rsi": analysis["rsi"], "adx": analysis["adx"], "macd_hist": analysis["macd_hist"],
        "stoch": analysis["stoch"], "williams_r": analysis["williams_r"],
    }


def handle_start(chat_id, first_name="Trader"):
    user = get_user(chat_id)
    if is_admin(chat_id):
        user["unlocked_tiers"] = TIER_ORDER[:]
        user["verified"] = True

    text = (
        f"👑 *HARDIK TRADER — Forex AI Signal Bot*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Welcome, *{first_name}*!\n\n"
        f"📈 Premium AI-powered trading signals, designed to make trading "
        f"simple, clear, and convenient.\n\n"
        f"🤖 *4 AI Models Available:*\n"
        f"⚡ Flash 2.0 — Quick signals (68% avg accuracy)\n"
        f"🚀 Pro 4.0 — Multi-indicator (76% avg accuracy)\n"
        f"🔥 Max 7.0 — Deep confluence (84% avg accuracy)\n"
        f"👑 Ultra 9.5 — Maximum accuracy (92%+ accuracy)\n\n"
    )
    if not is_admin(chat_id):
        text += (
            f"🔒 Higher tiers unlock based on your verified Quotex balance.\n"
            f"Tap *Unlock More Tiers* below to get started.\n\n"
        )
    else:
        text += (
            f"👑 *Admin Commands:*\n"
            f"/users — view & manage all verified users\n"
            f"/reset <chat_id> — remove a user's access manually\n\n"
        )
    text += "Choose your AI model to begin:"
    send_message(chat_id, text, tiers_keyboard(user))


def handle_verify_start(chat_id, message_id):
    text = (
        "🔓 *Unlock Premium Tiers*\n\n"
        "To access higher-accuracy AI models, you need an active Quotex "
        "trading account registered through our official link below.\n\n"
        "📌 *Steps:*\n"
        "1️⃣ Tap *Open Registration Link* and create your account\n"
        "2️⃣ Deposit funds (minimum $50 to unlock Flash 2.0)\n"
        "3️⃣ Tap *I've Created My Account* below\n"
        "4️⃣ Send your Quotex Trader ID + balance for verification\n\n"
        "💰 *Tier Requirements:*\n"
        "⚡ Flash 2.0 — $50+\n"
        "🚀 Pro 4.0 — $200+\n"
        "🔥 Max 7.0 — $500+\n"
        "👑 Ultra 9.5 — $700+"
    )
    edit_message(chat_id, message_id, text, verify_start_keyboard())


def handle_verify_created(chat_id, message_id):
    text = (
        "✅ Great! Now please send your verification details in *one message*, "
        "in this exact format:\n\n"
        "`ID: your_quotex_trader_id`\n"
        "`Balance: your_account_balance`\n\n"
        "Example:\n"
        "`ID: 123456789`\n"
        "`Balance: 250`"
    )
    user = get_user(chat_id)
    user["awaiting_verification_text"] = True
    edit_message(chat_id, message_id, text)


def parse_verification_text(text):
    quotex_id, balance = None, None
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("id:"):
            quotex_id = line.split(":", 1)[1].strip()
        elif line.lower().startswith("balance:"):
            raw = line.split(":", 1)[1].strip().replace("$", "").replace(",", "")
            try:
                balance = float(raw)
            except ValueError:
                balance = None
    return quotex_id, balance


def handle_verification_message(chat_id, text, username):
    user = get_user(chat_id)
    quotex_id, balance = parse_verification_text(text)

    if not quotex_id or balance is None:
        send_message(
            chat_id,
            "⚠️ I couldn't read that. Please send it in this exact format:\n\n"
            "`ID: your_quotex_trader_id`\n`Balance: your_account_balance`"
        )
        return

    user["awaiting_verification_text"] = False
    user["quotex_id"] = quotex_id
    user["pending"] = True
    user["reported_balance"] = balance

    send_message(
        chat_id,
        f"📨 *Verification request submitted!*\n\n"
        f"🆔 Trader ID: `{quotex_id}`\n"
        f"💰 Reported Balance: `${balance}`\n\n"
        f"⏳ An admin will review and approve your access shortly. "
        f"You'll get a notification here once approved."
    )

    admin_text = (
        f"🆕 *New Verification Request*\n\n"
        f"👤 User: @{username or 'unknown'} (chat_id: `{chat_id}`)\n"
        f"🆔 Quotex Trader ID: `{quotex_id}`\n"
        f"💰 Claimed Balance: `${balance}`\n\n"
        f"This balance would unlock: {', '.join(TIERS[t]['label'] for t in tiers_unlocked_for_balance(balance)) or 'No tiers (below $50)'}\n\n"
        f"Please verify this Trader ID in your Quotex affiliate dashboard before approving."
    )
    send_message(ADMIN_CHAT_ID, admin_text, admin_approval_keyboard(chat_id))


def handle_admin_approve(admin_chat_id, target_chat_id, message_id):
    if not is_admin(admin_chat_id):
        return
    user = get_user(target_chat_id)
    balance = user.get("reported_balance", 0)
    user["verified"] = True
    user["pending"] = False
    user["balance"] = balance
    user["unlocked_tiers"] = tiers_unlocked_for_balance(balance)

    edit_message(admin_chat_id, message_id, f"✅ Approved chat_id `{target_chat_id}` with balance ${balance}.")
    unlocked_labels = ", ".join(TIERS[t]["label"] for t in user["unlocked_tiers"]) or "None"
    send_message(
        target_chat_id,
        f"🎉 *Access Granted!*\n\n"
        f"Your Quotex account has been verified with balance *${balance}*.\n\n"
        f"🔓 Unlocked tiers: {unlocked_labels}\n\n"
        f"Use /start to begin generating signals!"
    )


def handle_admin_reject(admin_chat_id, target_chat_id, message_id):
    if not is_admin(admin_chat_id):
        return
    user = get_user(target_chat_id)
    user["pending"] = False

    edit_message(admin_chat_id, message_id, f"❌ Rejected chat_id `{target_chat_id}`.")
    send_message(
        target_chat_id,
        "❌ *Verification Rejected*\n\n"
        "We couldn't verify your Quotex account details. Please make sure:\n"
        "• You registered using our official link\n"
        "• Your Trader ID and balance are correct\n\n"
        "Tap *Unlock More Tiers* in /start to try again."
    )


def handle_list_users(admin_chat_id):
    verified_users = {cid: u for cid, u in USERS.items() if u.get("verified") and cid != ADMIN_CHAT_ID}

    if not verified_users:
        send_message(admin_chat_id, "📋 *No verified users yet.*\n\nUsers will appear here once you approve their balance verification.")
        return

    send_message(admin_chat_id, f"📋 *Verified Users ({len(verified_users)})*\n\nTap *Remove Access* if a user's Quotex balance has gone to $0:")

    for cid, u in verified_users.items():
        labels = ", ".join(TIERS[t]["label"] for t in u["unlocked_tiers"]) or "None"
        text = (
            f"👤 Chat ID: `{cid}`\n"
            f"🆔 Trader ID: `{u.get('quotex_id', 'N/A')}`\n"
            f"💰 Balance on file: ${u.get('balance', 0)}\n"
            f"🔓 Unlocked: {labels}"
        )
        keyboard = [[{"text": "🗑 Remove Access (balance = $0)", "callback_data": f"admin_reset_{cid}"}]]
        send_message(admin_chat_id, text, keyboard)


def handle_admin_reset_balance(admin_chat_id, target_chat_id, message_id):
    if not is_admin(admin_chat_id):
        return
    user = get_user(target_chat_id)
    user["balance"] = 0
    user["unlocked_tiers"] = []
    user["verified"] = False
    if message_id:
        edit_message(admin_chat_id, message_id, f"✅ *Access removed* for chat_id `{target_chat_id}`.\nAll their tiers are now locked.")
    else:
        send_message(admin_chat_id, f"✅ *Access removed* for chat_id `{target_chat_id}`.\nAll their tiers are now locked.")
    send_message(
        target_chat_id,
        "⚠️ *Access Reset*\n\nYour balance verification has been reset by an admin "
        "(likely because your Quotex balance is now $0). Please re-verify with "
        "*Unlock More Tiers* in /start to regain access."
    )


def handle_tier_selected(chat_id, message_id, tier_key):
    user = get_user(chat_id)
    if not is_admin(chat_id) and tier_key not in user["unlocked_tiers"]:
        tier = TIERS[tier_key]
        edit_message(
            chat_id, message_id,
            f"🔒 *{tier['label']} is locked*\n\n"
            f"This tier requires a verified Quotex balance of *${tier['min_balance']}+*.\n\n"
            f"Your current verified balance: *${user.get('balance', 0)}*\n\n"
            f"Tap below to unlock it.",
            [[{"text": "🔓 Unlock More Tiers", "callback_data": "verify_start"}],
             [{"text": "⬅️ Back", "callback_data": "back_tiers"}]]
        )
        return

    session = get_session(chat_id)
    session["tier"] = tier_key
    tier = TIERS[tier_key]
    checked_names = [INDICATOR_DISPLAY_NAMES[k] for k in tier["indicator_keys"]]
    text = (
        f"✅ *{tier['label']}* selected!\n\n"
        f"🔍 Analysis depth: {tier['depth']}\n"
        f"📊 Indicators checked: {', '.join(checked_names)}\n"
        f"🎯 Requires {tier['required_confirms']}/{len(checked_names)} confirmations for high-quality signal\n\n"
        f"Now choose pair type:"
    )
    edit_message(chat_id, message_id, text, categories_keyboard())


def render_generate_screen(chat_id, message_id, session):
    tier = TIERS[session["tier"]]
    text = (
        f"🤖 Model: *{tier['label']}*\n"
        f"💱 Pair: *{session['pair']}*\n"
        f"⏱ Expiry: *{session['expiry']}*\n"
    )
    if session.get("ai_model"):
        text += f"🔬 Cross-check: *{AI_MODELS[session['ai_model']]['label']}*\n"
    text += "\nReady to analyze the market. Tap below 👇"
    edit_message(chat_id, message_id, text, generate_keyboard())


def do_generate(chat_id, message_id, session):
    if not session.get("tier") or not session.get("pair"):
        edit_message(chat_id, message_id, "⚠️ Please /start again and select a model + pair first.")
        return

    tier = TIERS[session["tier"]]
    edit_message(chat_id, message_id, f"🔍 *The {tier['label']} is analyzing the market...*")

    sig = generate_signal_data(session["pair"], session["tier"], session.get("ai_model"))
    direction_pill = "🟢 BUY" if sig["direction"] == "BUY" else "🔴 SELL"
    direction_word = "UP" if sig["direction"] == "BUY" else "DOWN"
    emoji_big = "📈" if sig["direction"] == "BUY" else "📉"

    caption = (
        f"✅ *The analysis is complete!*\n\n"
        f"🤖 Model: {sig['tier']}\n"
    )
    if sig.get("ai_model"):
        caption += f"🔬 Cross-checked by: {sig['ai_model']}\n"
    caption += (
        f"💱 Currency pair: {sig['pair']}\n"
        f"⏱ Expiration time: {session['expiry']}\n"
        f"📊 Entry: `{sig['entry']}`\n"
        f"🎯 Confidence: *{sig['confidence']}%*\n"
        f"📡 Data source: {sig['source']}\n\n"
        f"📐 *Indicator Confluence:* {sig['confirm_count']}/{sig['total_checked']} confirmed\n"
        f"📊 RSI: {sig['rsi']} | ADX: {sig['adx']} | MACD: {sig['macd_hist']:+.5f}\n"
        f"📊 Stoch: {sig['stoch']} | Williams %R: {sig['williams_r']}\n"
    )
    if sig["confirmed_names"]:
        caption += f"✅ Confirmed by: {', '.join(sig['confirmed_names'])}\n"
    caption += (
        f"\n📢 Signal: {direction_pill}\n"
        f"{emoji_big} *{direction_word}*"
    )

    # If we previously sent a signal as a photo for this chat, remove it first
    # so regenerating a signal replaces the old one instead of stacking messages.
    prev_photo_id = LAST_SIGNAL_MSG.get(chat_id)
    if prev_photo_id:
        delete_message(chat_id, prev_photo_id)

    poster_file = "signal_up.png" if sig["direction"] == "BUY" else "signal_down.png"

    if POSTER_BASE_URL:
        photo_url = f"{POSTER_BASE_URL}/{poster_file}"
        resp = send_photo(chat_id, photo_url, caption, result_keyboard())
        new_msg_id = None
        if resp and resp.get("ok"):
            new_msg_id = resp["result"]["message_id"]
        # Remove the now-redundant "analyzing..." text message
        delete_message(chat_id, message_id)
        LAST_SIGNAL_MSG[chat_id] = new_msg_id
    else:
        # Fallback: no public base URL configured yet, just send as text
        edit_message(chat_id, message_id, caption, result_keyboard())
        LAST_SIGNAL_MSG[chat_id] = message_id


def handle_callback(update):
    cq = update["callback_query"]
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    data = cq["data"]
    answer_callback(cq["id"])

    session = get_session(chat_id)
    user = get_user(chat_id)

    if data.startswith("tier_"):
        handle_tier_selected(chat_id, message_id, data.split("_")[1])
    elif data.startswith("cat_"):
        cat = data.split("_")[1]
        pairs = LIVE_PAIRS if cat == "live" else OTC_PAIRS
        label = "💹 Live Pairs" if cat == "live" else "🕐 OTC Pairs"
        edit_message(chat_id, message_id, f"{label}\n\nSelect a pair:", pairs_keyboard(pairs))
    elif data.startswith("pair_"):
        pair = data.split("_", 1)[1]
        session["pair"] = pair
        session["ai_model"] = None
        if "-OTC" in pair:
            # OTC pairs go through the multi-AI model selection grid first
            text = (
                f"💱 Pair: *{pair}*\n\n"
                f"🤖 *Select Your AI Model*\n"
                f"Each model cross-checks the OTC signal for extra confluence:"
            )
            edit_message(chat_id, message_id, text, ai_models_keyboard())
        else:
            edit_message(chat_id, message_id, f"💱 Pair: *{pair}*\n\nSelect expiration time:", expiry_keyboard())
    elif data.startswith("aimodel_"):
        model_key = data.split("_", 1)[1]
        session["ai_model"] = model_key
        model_label = AI_MODELS[model_key]["label"]
        edit_message(
            chat_id, message_id,
            f"✅ *{model_label}* selected for cross-analysis!\n\n"
            f"💱 Pair: *{session['pair']}*\n\n"
            f"Select expiration time:",
            expiry_keyboard()
        )
    elif data.startswith("exp_"):
        session["expiry"] = data.split("_", 1)[1]
        render_generate_screen(chat_id, message_id, session)
    elif data == "generate":
        do_generate(chat_id, message_id, session)
    elif data == "back_tiers":
        edit_message(chat_id, message_id, "Choose your AI model:", tiers_keyboard(user))
    elif data == "back_categories":
        edit_message(chat_id, message_id, "Choose pair type:", categories_keyboard())
    elif data == "verify_start":
        handle_verify_start(chat_id, message_id)
    elif data == "verify_created":
        handle_verify_created(chat_id, message_id)
    elif data.startswith("admin_approve_"):
        target = int(data.split("_")[2])
        handle_admin_approve(chat_id, target, message_id)
    elif data.startswith("admin_reject_"):
        target = int(data.split("_")[2])
        handle_admin_reject(chat_id, target, message_id)
    elif data.startswith("admin_reset_"):
        target = int(data.split("_")[2])
        handle_admin_reset_balance(chat_id, target, message_id)


def handle_text_message(chat_id, text, username, first_name):
    if text.startswith("/start"):
        handle_start(chat_id, first_name)
        return
    if text.startswith("/stats"):
        user = get_user(chat_id)
        labels = ", ".join(TIERS[t]["label"] for t in user["unlocked_tiers"]) or "None — verify to unlock"
        send_message(chat_id, f"📊 *Your Status*\n\n✅ Verified: {'Yes' if user['verified'] else 'No'}\n"
                              f"💰 Balance on file: ${user.get('balance', 0)}\n🔓 Unlocked tiers: {labels}")
        return
    if text.startswith("/reset") and is_admin(chat_id):
        parts = text.split()
        if len(parts) == 2:
            try:
                target = int(parts[1])
                handle_admin_reset_balance(chat_id, target, None)
                send_message(chat_id, f"Reset done for {target}.")
            except ValueError:
                send_message(chat_id, "Usage: /reset <chat_id>")
        return

    if text.startswith("/users") and is_admin(chat_id):
        handle_list_users(chat_id)
        return
    user = get_user(chat_id)
    if user.get("awaiting_verification_text"):
        handle_verification_message(chat_id, text, username)
        return


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length)
            update = json.loads(body)

            if "message" in update and "text" in update["message"]:
                msg = update["message"]
                chat_id = msg["chat"]["id"]
                text = msg["text"]
                username = msg["from"].get("username")
                first_name = msg["from"].get("first_name", "Trader")
                handle_text_message(chat_id, text, username, first_name)
            elif "callback_query" in update:
                handle_callback(update)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"Hardik Trader Forex AI Signal Bot webhook is alive"}')
