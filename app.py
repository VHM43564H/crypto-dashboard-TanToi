"""
Crypto Dashboard Pro
Ứng dụng Streamlit phân tích crypto chuyên nghiệp với đúng 3 tab.

Yêu cầu đã đáp ứng:
- st.tabs() chính xác 3 tab
- Tab 1: Top 20 từ CoinGecko, Top 5 metric cards + sortable dataframe (có màu emoji)
- Tab 2: Dropdown coin, timeframe 30/90/180/365, Plotly candlestick + TẤT CẢ chỉ báo (EMA, SMA, RSI, MACD, Ichimoku đầy đủ)
  + Toggles bật/tắt từng chỉ báo
- Tab 3: Tin tức từ CryptoCompare public API (không key), 10-15 bài, link, time ago
- @st.cache_data cho TẤT CẢ API calls
- Disclaimer mạnh ở mọi tab + footer
- Giao diện tiếng Việt, theme tối chuyên nghiệp
- Comment chi tiết để học tập

Chạy: streamlit run app.py
"""

# =============================================================================
# 1. IMPORTS + CẤU HÌNH TRANG (QUAN TRỌNG: set_page_config PHẢI LÀ LỆNH STREAMLIT ĐẦU TIÊN)
# =============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import feedparser

# st.set_page_config MUST be the VERY FIRST Streamlit command (right after ALL imports, before any other st.*)
st.set_page_config(title="Crypto Dashboard Pro", layout="wide", page_icon="")

# CSS tùy chỉnh cho theme crypto hiện đại + đẹp hơn
st.markdown("""
<style>
    /* Nền và chữ tổng thể */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Metric cards đẹp hơn */
    [data-testid="metric-container"] {
        background-color: #1a1d24;
        border: 1px solid #2a2d35;
        border-radius: 12px;
        padding: 12px 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    /* Tiêu đề tab */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1d24;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #00ff9f20;
        border-bottom: 3px solid #00ff9f;
    }
    
    /* Dataframe */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #2a2d35;
    }
    
    /* Nút chính */
    .stButton > button {
        background: linear-gradient(90deg, #00ff9f, #00cc7a);
        color: #0e1117;
        font-weight: 700;
        border: none;
        border-radius: 8px;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 255, 159, 0.4);
    }
    
    /* Disclaimer box */
    .disclaimer-box {
        background-color: #2a2d1f;
        border-left: 5px solid #ffcc00;
        padding: 12px 16px;
        border-radius: 6px;
        margin: 12px 0;
        font-size: 0.92rem;
        line-height: 1.4;
    }
    
    /* Link và caption */
    a {
        color: #00ff9f !important;
    }
    
    /* Giảm khoảng cách thừa */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# FALLBACK COINS (for Tab 2 dropdown to keep UI 100% identical before lazy Top20 load)
# =============================================================================

DEFAULT_COIN_OPTIONS = [
    "Bitcoin (BTC)", "Ethereum (ETH)", "BNB (BNB)", "Solana (SOL)", "XRP (XRP)",
    "Dogecoin (DOGE)", "Cardano (ADA)", "Avalanche (AVAX)", "Shiba Inu (SHIB)",
    "Polkadot (DOT)", "Chainlink (LINK)", "Litecoin (LTC)", "Bitcoin Cash (BCH)",
    "Uniswap (UNI)", "Stellar (XLM)", "Monero (XMR)", "Ethereum Classic (ETC)",
    "Filecoin (FIL)", "Cosmos (ATOM)", "VeChain (VET)"
]
DEFAULT_SYMBOL_MAP = {opt: opt.split("(")[1].replace(")", "") for opt in DEFAULT_COIN_OPTIONS}


# =============================================================================
# 3. HÀM HELPER (FORMAT + TIME AGO + TÍNH CHỈ BÁO)
# =============================================================================

def format_large_number(num: float) -> str:
    """Format số lớn thành dạng 1.23B, 456.7M (dùng cho Volume & Market Cap)."""
    if pd.isna(num) or num is None:
        return "N/A"
    if num >= 1_000_000_000:
        return f"${num/1_000_000_000:.2f}B"
    if num >= 1_000_000:
        return f"${num/1_000_000:.1f}M"
    return f"${num:,.0f}"


def get_time_ago_vn(unix_timestamp: int) -> str:
    """
    Chuyển unix timestamp (giây) thành chuỗi tiếng Việt 'X phút trước'.
    Dùng cho Tab 3.
    """
    if not unix_timestamp:
        return "không rõ"
    now = datetime.utcnow().timestamp()
    diff_seconds = now - int(unix_timestamp)

    if diff_seconds < 60:
        return f"{int(diff_seconds)} giây trước"
    elif diff_seconds < 3600:
        return f"{int(diff_seconds // 60)} phút trước"
    elif diff_seconds < 86400:
        return f"{int(diff_seconds // 3600)} giờ trước"
    else:
        return f"{int(diff_seconds // 86400)} ngày trước"


# ------------------ CÁC HÀM TÍNH CHỈ BÁO KỸ THUẬT (THỦ CÔNG - GIÁO DỤC) ------------------

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average = trung bình trượt đơn giản (cộng dồn / n)."""
    return series.rolling(window=period, min_periods=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """
    Exponential Moving Average.
    Công thức: EMA_t = Giá_t * k + EMA_{t-1} * (1-k)   với k = 2/(period+1)
    Pandas ewm(span=period) đã implement chuẩn.
    """
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (RSI) 14 kỳ - Wilder.
    Bước:
      1. Tính delta = close.diff()
      2. Gain = delta nếu >0 else 0, trung bình rolling
      3. Loss = -delta nếu <0 else 0, trung bình rolling
      4. RS = Gain / Loss
      5. RSI = 100 - 100/(1+RS)
    Giá trị >70: quá mua, <30: quá bán.
    """
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    MACD (Moving Average Convergence Divergence)
    MACD Line   = EMA12 - EMA26
    Signal Line = EMA9 của MACD Line
    Histogram   = MACD Line - Signal Line
    Histogram >0 + MACD cắt lên Signal = tín hiệu tăng mạnh.
    """
    ema_fast = calculate_ema(df["close"], fast)
    ema_slow = calculate_ema(df["close"], slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_ichimoku(df: pd.DataFrame, tenkan: int = 9, kijun: int = 26,
                       senkou_b_period: int = 52, displacement: int = 26):
    """
    ICHIMOKU CLOUD - Hệ thống chỉ báo toàn diện (Ichimoku Kinko Hyo).
    5 thành phần chuẩn:
      - Tenkan-sen  (Conversion Line): (Highest High + Lowest Low)/2 của 9 kỳ
      - Kijun-sen   (Base Line):       (Highest High + Lowest Low)/2 của 26 kỳ
      - Senkou Span A: (Tenkan + Kijun)/2  → dịch chuyển +26 kỳ vào TƯƠNG LAI
      - Senkou Span B: (HH + LL)/2 của 52 kỳ → dịch +26 kỳ vào TƯƠNG LAI
      - Chikou Span: Giá Close hiện tại → dịch -26 kỳ vào QUÁ KHỨ
    Mây (Cloud) = vùng giữa Senkou A và B. Giá trên mây = xu hướng tăng.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # 1. Tenkan-sen (9)
    period_high_tenkan = high.rolling(window=tenkan, min_periods=tenkan).max()
    period_low_tenkan = low.rolling(window=tenkan, min_periods=tenkan).min()
    tenkan_sen = (period_high_tenkan + period_low_tenkan) / 2

    # 2. Kijun-sen (26)
    period_high_kijun = high.rolling(window=kijun, min_periods=kijun).max()
    period_low_kijun = low.rolling(window=kijun, min_periods=kijun).min()
    kijun_sen = (period_high_kijun + period_low_kijun) / 2

    # 3. Senkou Span A (dịch +displacement)
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(displacement)

    # 4. Senkou Span B (52)
    period_high_b = high.rolling(window=senkou_b_period, min_periods=senkou_b_period).max()
    period_low_b = low.rolling(window=senkou_b_period, min_periods=senkou_b_period).min()
    senkou_span_b = ((period_high_b + period_low_b) / 2).shift(displacement)

    # 5. Chikou Span (dịch -displacement)
    chikou_span = close.shift(-displacement)

    return tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span


# =============================================================================
# 4. CÁC HÀM FETCH DỮ LIỆU (CÓ @st.cache_data)
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_top_coins() -> pd.DataFrame:
    """
    Lấy Top 20 coin theo market cap từ CoinGecko public API (không cần key).
    Trả về DataFrame với các cột cần thiết + 24h% và 7d%.
    Cache 5 phút. KHÔNG gọi st.* bên trong (tránh side-effect khi cache).
    """
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 20,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h,7d"
    }
    try:
        resp = requests.get(url, params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data)

        # Giữ các cột quan trọng
        keep_cols = [
            "market_cap_rank", "id", "symbol", "name", "image",
            "current_price", "price_change_percentage_24h",
            "price_change_percentage_7d", "total_volume", "market_cap"
        ]
        df = df[[c for c in keep_cols if c in df.columns]].copy()
        df = df.dropna(subset=["market_cap_rank"])
        df["market_cap_rank"] = df["market_cap_rank"].astype(int)
        return df
    except Exception:
        # Trả rỗng; caller sẽ hiển thị lỗi nếu cần. Không gọi st.* ở đây.
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_daily_klines(coin_symbol: str, days: int = 90) -> pd.DataFrame:
    """
    Lấy dữ liệu nến DAILY từ Binance public API (không key).
    Ưu tiên Binance vì cho nến daily sạch, đủ cho mọi chỉ báo (SMA200, Ichimoku 52+).
    Nếu thất bại (coin hiếm), fallback sang CoinGecko /ohlc (granularity thô hơn).

    Trả về DataFrame: index datetime, cột ['open','high','low','close']
    Cache 5 phút. KHÔNG gọi st.* bên trong.
    """
    symbol = coin_symbol.upper()
    binance_symbol = f"{symbol}USDT"

    # --- 1. Thử Binance trước ---
    try:
        limit = min(days, 1000)
        url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval=1d&limit={limit}"
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200:
            raw = resp.json()
            if raw and len(raw) > 5:
                df = pd.DataFrame(raw, columns=[
                    "open_time", "open", "high", "low", "close", "volume",
                    "close_time", "quote_asset_volume", "trades",
                    "taker_buy_base", "taker_buy_quote", "ignore"
                ])
                df = df[["open_time", "open", "high", "low", "close"]].copy()
                for col in ["open", "high", "low", "close"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df["date"] = pd.to_datetime(df["open_time"], unit="ms")
                df = df.set_index("date")[["open", "high", "low", "close"]]
                df = df.dropna()
                if len(df) >= 10:
                    return df
    except Exception:
        pass  # fallback ngay

    # --- 2. Fallback: CoinGecko /ohlc (chấp nhận granularity thô cho >30d) ---
    try:
        # Lấy coin_id từ symbol (đơn giản, dùng mapping nhỏ)
        # Thực tế ta sẽ truyền coin_id từ top20_df
        # Ở đây giả định caller truyền symbol, ta thử map phổ biến
        coin_id_map = {
            "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
            "SOL": "solana", "XRP": "ripple", "DOGE": "dogecoin",
            "ADA": "cardano", "AVAX": "avalanche-2", "SHIB": "shiba-inu"
        }
        coin_id = coin_id_map.get(symbol, symbol.lower())
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": str(days)}
        resp = requests.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            raw = resp.json()  # [[timestamp, o, h, l, c], ...]
            if raw and len(raw) > 5:
                df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close"])
                df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("date")[["open", "high", "low", "close"]]
                df = df.dropna()
                return df
    except Exception:
        pass  # nuốt lỗi, trả rỗng ở cuối

    # Trả về rỗng nếu cả hai đều fail
    return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_crypto_news(limit: int = 15) -> list:
    """
    Lấy tin tức crypto mới nhất từ CryptoCompare (public, không cần API key).
    Trả về list dict: title, source_info{name}, published_on, body, url

    Xử lý lỗi mạnh mẽ:
    - Kiểm tra response là dict
    - Kiểm tra key 'Data' TỒN TẠI và GIÁ TRỊ LÀ LIST (tránh lỗi slice(None,15,None) khi API trả None hoặc dict)
    - Nếu bất kỳ lỗi nào (mạng, timeout, JSON, cấu trúc sai, rate-limit...) → trả về 5 tin mẫu tiếng Việt (fallback)
    Không gọi st.error/st.warning bên trong hàm cache để tránh làm bẩn UI.
    Cache 5 phút.
    """
    url = "https://min-api.cryptocompare.com/data/v2/news/"
    params = {"lang": "EN", "sortOrder": "latest"}

    try:
        resp = requests.get(url, params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()

        # === KIỂM TRA AN TOÀN BẮT BUỘC (sửa lỗi gốc) ===
        if isinstance(data, dict):
            articles = data.get("Data")
            if isinstance(articles, list) and len(articles) > 0:
                # Chỉ lấy những bài có title hợp lệ
                valid = [a for a in articles[:limit] if isinstance(a, dict) and a.get("title")]
                if valid:
                    return valid
    except Exception:
        # Nuốt toàn bộ lỗi: network, JSONDecode, timeout, HTTP error, v.v.
        # Chủ động fallback thay vì crash hoặc hiện lỗi thô
        pass

    # ==================== 5 TIN TỨC MẪU THAM KHẢO (TIẾNG VIỆT) ====================
    now = int(datetime.utcnow().timestamp())
    fallback_news = [
        {
            "title": "Bitcoin vượt mốc 108.000 USD, lập kỷ lục giá mọi thời đại mới",
            "source_info": {"name": "Crypto Dashboard (Mẫu)"},
            "published_on": now - 2400,   # ~40 phút trước
            "body": "Giá Bitcoin đã chính thức chạm mức cao mới lịch sử sau khi các quỹ ETF Bitcoin spot ghi nhận dòng vốn mạnh từ nhà đầu tư tổ chức. Nhiều chuyên gia cho rằng ngưỡng 120.000 USD có thể được chạm trong vòng 30-60 ngày tới nếu đà tăng được duy trì.",
            "url": "#",
        },
        {
            "title": "Ethereum ETF thu hút hơn 1,5 tỷ USD chỉ trong 7 ngày đầu ra mắt",
            "source_info": {"name": "Crypto Dashboard (Mẫu)"},
            "published_on": now - 5400,   # ~1.5 giờ trước
            "body": "Sự kiện Ethereum ETF spot được phê duyệt đã tạo hiệu ứng tích cực mạnh mẽ. BlackRock và Fidelity dẫn đầu danh sách các quỹ có lượng nắm giữ ETH lớn nhất. Giá ETH tăng hơn 8% trong 24h qua.",
            "url": "#",
        },
        {
            "title": "Solana phá vỡ 250 USD, hệ sinh thái DeFi và Memecoin bùng nổ",
            "source_info": {"name": "Crypto Dashboard (Mẫu)"},
            "published_on": now - 9000,   # ~2.5 giờ trước
            "body": "Solana tiếp tục là blockchain tăng trưởng nhanh nhất 2025. TVL trên hệ sinh thái DeFi của Solana đã vượt 12 tỷ USD. Hàng loạt memecoin mới ra đời trên Solana đang thu hút dòng tiền đầu cơ ngắn hạn.",
            "url": "#",
        },
        {
            "title": "Fed giữ nguyên lãi suất, thị trường crypto phản ứng tích cực mạnh",
            "source_info": {"name": "Crypto Dashboard (Mẫu)"},
            "published_on": now - 14400,  # 4 giờ trước
            "body": "Quyết định không tăng lãi suất của Cục Dự trữ Liên bang Mỹ đã giúp tài sản rủi ro như cổ phiếu công nghệ và crypto phục hồi. Bitcoin và các altcoin lớn đều ghi nhận mức tăng 3-7% trong phiên giao dịch gần nhất.",
            "url": "#",
        },
        {
            "title": "Binance ra mắt chương trình hỗ trợ AI cho giao dịch crypto tự động",
            "source_info": {"name": "Crypto Dashboard (Mẫu)"},
            "published_on": now - 21600,  # 6 giờ trước
            "body": "Binance chính thức giới thiệu công cụ AI trading mới tích hợp phân tích on-chain và tín hiệu kỹ thuật. Người dùng VIP có thể sử dụng miễn phí trong 3 tháng đầu. Đây được xem là bước tiến lớn trong việc dân chủ hóa giao dịch thuật toán.",
            "url": "#",
        },
    ]
    return fallback_news


# =============================================================================
# 4b. HÀM MỚI CHO TAB 3: TIN TỨC KINH TẾ - TÀI CHÍNH VIỆT NAM (RSS)
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_vietnam_econ_news(limit: int = 12) -> list:
    """
    Lấy tin tức Kinh tế - Tài chính Việt Nam mới nhất từ 4 nguồn RSS uy tín.
    Luôn cố gắng lấy dữ liệu LIVE từ RSS trước. Không dùng tin mẫu cố định.

    Trả về list dict chuẩn: title, source, published_ts, summary, url

    Xử lý lỗi CỰC MẠNH (bọc ngoài cùng):
    - Mọi lỗi (network, parse, timeout, feedparser, sort, ...) → nuốt sạch, trả [] 
    - KHÔNG BAO GIỜ raise exception ra ngoài (tránh crash app + healthz fail trên Streamlit Cloud)
    Cache 5 phút (ttl=300).
    """
    try:
        feeds = {
            "VNExpress Kinh doanh": "https://vnexpress.net/rss/kinh-doanh.rss",
            "Tuổi Trẻ Kinh doanh": "https://tuoitre.vn/rss/kinh-doanh.rss",
            "CafeF": "https://cafef.vn/rss/kinh-te.rss",
            "VnEconomy": "https://vneconomy.vn/rss/kinh-te.rss",
        }

        articles = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        }

        for source_name, url in feeds.items():
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    continue
                feed = feedparser.parse(resp.content)
                entries = getattr(feed, "entries", None) or []
                for entry in entries[:6]:
                    try:
                        title = (entry.get("title") or "").strip()
                        link = (entry.get("link") or "").strip()
                        if not title or not link:
                            continue

                        # published time
                        published_ts = 0
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                published_ts = int(time.mktime(entry.published_parsed))
                            except Exception:
                                published_ts = 0
                        elif entry.get("published"):
                            try:
                                from email.utils import parsedate_to_datetime
                                dt = parsedate_to_datetime(entry.get("published"))
                                published_ts = int(dt.timestamp())
                            except Exception:
                                published_ts = 0

                        # summary ngắn gọn
                        summary = entry.get("summary") or entry.get("description") or ""
                        summary = " ".join(str(summary).split())[:280]
                        if "<" in summary and ">" in summary:
                            import re
                            summary = re.sub(r"<[^>]+>", " ", summary)
                            summary = " ".join(summary.split())[:280]

                        articles.append({
                            "title": title,
                            "source": source_name,
                            "published_ts": published_ts,
                            "summary": summary,
                            "url": link,
                        })
                    except Exception:
                        continue
            except Exception:
                continue

        # Sắp xếp mới nhất trước
        articles.sort(key=lambda x: x.get("published_ts", 0), reverse=True)

        # Loại trùng
        seen = set()
        unique_articles = []
        for a in articles:
            key = (a.get("url") or "") + (a.get("title") or "")
            if key not in seen:
                seen.add(key)
                unique_articles.append(a)

        # CHỈ trả về bài thật. Không bao giờ trả sample cố định.
        return unique_articles[:limit]
    except Exception:
        # Bọc ngoài cùng: tuyệt đối an toàn, không crash app dù RSS có vấn đề gì
        return []


# =============================================================================
# 5. HÀM HIỂN THỊ DISCLAIMER (DÙNG LẠI Ở MỌI TAB)
# =============================================================================

def show_strong_disclaimer():
    """Hiển thị disclaimer mạnh, rõ ràng, lặp lại ở mọi nơi theo yêu cầu."""
    st.markdown("""
    <div class="disclaimer-box">
        <b>⚠️ TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM</b><br>
        Ứng dụng này <b>chỉ mang tính tham khảo, giáo dục và giải trí</b>. 
        <b>Không phải lời khuyên tài chính, đầu tư, giao dịch hay pháp lý</b>.<br>
        Giá tiền điện tử biến động cực mạnh. Bạn có thể mất <b>toàn bộ vốn đầu tư</b>. 
        Dữ liệu từ API công khai có thể chậm trễ hoặc không chính xác 100%. 
        <b>Luôn tự nghiên cứu kỹ (DYOR)</b>. Tác giả và các nguồn dữ liệu không chịu trách nhiệm 
        về bất kỳ thiệt hại trực tiếp hay gián tiếp nào phát sinh từ việc sử dụng thông tin tại đây.
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# 6. MAIN APPLICATION
# =============================================================================

def main():
    # Header (luôn nhanh, không network)
    st.title("📊 Crypto Dashboard Pro")
    st.markdown(
        "Dữ liệu thời gian thực từ **CoinGecko** • **Binance** • **CryptoCompare** &nbsp;|&nbsp; "
        "Cập nhật với cache thông minh &nbsp;|&nbsp; <span style='color:#00ff9f'>Phiên bản 1.0</span>"
    )

    # Khởi tạo session state cho lazy loading — KHÔNG fetch gì ở đây (quan trọng cho healthz)
    if "top_coins_df" not in st.session_state:
        st.session_state["top_coins_df"] = pd.DataFrame()
    if "chart_loaded" not in st.session_state:
        st.session_state["chart_loaded"] = False
    # tab3_news_loaded và tab3_news_articles được xử lý bên trong tab3

    # =============================================================================
    # TẠO 3 TABS (YÊU CẦU CHÍNH XÁC: st.tabs) — skeleton ngay, data chỉ khi user click refresh
    # =============================================================================
    tab1, tab2, tab3 = st.tabs([
        "📊 Giá biến động Top 20 Coin",
        "📉 Phân tích Kỹ thuật",
        "📰 Tin tức Kinh tế - Tài chính Việt Nam"
    ])

    # ==========================================================================
    # TAB 1: GIÁ BIẾN ĐỘNG TOP 20 COIN
    # ==========================================================================
    with tab1:
        st.header("📊 Giá biến động Top 20 Coin theo Market Cap")
        st.caption("Nguồn: CoinGecko Public API • Cập nhật mỗi ~5 phút (cache)")

        # Nút cập nhật dữ liệu — CHỈ KHI CLICK NÚT NÀY MỚI GỌI FETCH (lazy hoàn toàn)
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            if st.button("🔄 Cập nhật dữ liệu", type="primary", key="refresh_tab1"):
                st.cache_data.clear()
                with st.spinner("Đang tải dữ liệu..."):
                    st.session_state["top_coins_df"] = fetch_top_coins()

        with col_info:
            st.caption(f"Top 20 coin • Hiển thị thay đổi giá 24h & 7d • Dữ liệu gần nhất: {datetime.now().strftime('%H:%M:%S')}")

        # === LAZY: chỉ render dữ liệu sau khi user click nút (top_coins_df được nạp vào session) ===
        top_coins_df = st.session_state.get("top_coins_df", pd.DataFrame())
        if top_coins_df.empty:
            st.info("📌 Nhấn nút **Cập nhật dữ liệu** bên trên để tải Top 20 coin từ CoinGecko. Dữ liệu chỉ fetch khi bạn yêu cầu — giúp app chạy ổn định trên Streamlit Cloud.")
            show_strong_disclaimer()
        else:
            # --- TOP 5 METRIC CARDS ---
            st.subheader("🔥 Top 5 Coin nổi bật")
            top5 = top_coins_df.head(5).reset_index(drop=True)

            cols = st.columns(5)
            for idx, row in top5.iterrows():
                with cols[idx]:
                    chg = row.get("price_change_percentage_24h", 0) or 0
                    delta_color = "normal" if chg >= 0 else "inverse"
                    st.metric(
                        label=f"#{row['market_cap_rank']} {row['name']}",
                        value=f"${row['current_price']:,.2f}",
                        delta=f"{chg:.2f}%",
                        delta_color=delta_color
                    )

            st.divider()

            # --- FULL SORTABLE DATAFRAME ---
            st.subheader("📋 Bảng dữ liệu đầy đủ (Sortable)")

            # Chuẩn bị dataframe hiển thị tiếng Việt + emoji
            display_df = pd.DataFrame({
                "Hạng": top_coins_df["market_cap_rank"],
                "Coin": top_coins_df["name"] + " (" + top_coins_df["symbol"].str.upper() + ")",
                "Giá (USD)": top_coins_df["current_price"],
                "24h %": top_coins_df["price_change_percentage_24h"].round(2),
                "7d %": top_coins_df.get("price_change_percentage_7d", pd.Series([0]*len(top_coins_df))).round(2),
                "Volume 24h": top_coins_df["total_volume"].apply(format_large_number),
                "Market Cap": top_coins_df["market_cap"].apply(format_large_number),
                "Xu hướng": np.where(
                    top_coins_df["price_change_percentage_24h"].fillna(0) >= 0, "🟢", "🔴"
                )
            })

            # Hiển thị với column_config đẹp
            st.dataframe(
                display_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Giá (USD)": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Giá hiện tại theo USD"
                    ),
                    "24h %": st.column_config.NumberColumn(
                        format="%.2f%%",
                        help="Thay đổi giá trong 24 giờ qua"
                    ),
                    "7d %": st.column_config.NumberColumn(
                        format="%.2f%%",
                        help="Thay đổi giá trong 7 ngày qua"
                    ),
                    "Volume 24h": st.column_config.TextColumn(help="Khối lượng giao dịch 24h"),
                    "Market Cap": st.column_config.TextColumn(help="Vốn hóa thị trường"),
                }
            )

            st.caption("💡 Mẹo: Click tiêu đề cột để sắp xếp tăng/giảm. Emoji 🟢 = tăng, 🔴 = giảm (24h).")

            show_strong_disclaimer()

    # ==========================================================================
    # TAB 2: PHÂN TÍCH KỸ THUẬT (CANDLES + TOÀN BỘ CHỈ BÁO + TOGGLE)
    # ==========================================================================
    with tab2:
        st.header("📉 Phân tích Kỹ thuật Tương tác")
        st.caption("Nến Daily từ Binance Public API (chất lượng cao) • Tính chỉ báo thủ công bằng pandas")

        # --- XÂY DỰNG OPTIONS/MAP CHO DROPDOWN (ưu tiên live Top20 nếu đã load ở Tab1, fallback để UI y nguyên) ---
        live_df = st.session_state.get("top_coins_df", pd.DataFrame())
        if isinstance(live_df, pd.DataFrame) and not live_df.empty:
            coin_options = [
                f"{row['name']} ({row['symbol'].upper()})"
                for _, row in live_df.iterrows()
            ]
            coin_symbol_map = {f"{row['name']} ({row['symbol'].upper()})": row['symbol']
                               for _, row in live_df.iterrows()}
        else:
            coin_options = DEFAULT_COIN_OPTIONS
            coin_symbol_map = DEFAULT_SYMBOL_MAP

        # --- CONTROLS (giữ nguyên thứ tự widget để UI 100% giống) ---
        ctrl_col1, ctrl_col2 = st.columns([2.2, 1.3])

        with ctrl_col1:
            selected_label = st.selectbox(
                "🔎 Chọn coin từ Top 20",
                options=coin_options,
                index=0,
                help="Chọn coin để xem biểu đồ kỹ thuật chi tiết"
            )

        with ctrl_col2:
            timeframe_days = st.selectbox(
                "📅 Timeframe (ngày)",
                options=[30, 90, 180, 365],
                index=1,  # mặc định 90 ngày
                help="Số ngày dữ liệu nến daily. 365 ngày tốt nhất cho SMA200 & Ichimoku."
            )

        # --- TOGGLES CHỈ BÁO ---
        st.markdown("**⚙️ Bật / Tắt chỉ báo (tương tác realtime):**")
        tog_col1, tog_col2, tog_col3 = st.columns(3)

        with tog_col1:
            show_ema9 = st.checkbox("EMA 9", value=True)
            show_ema21 = st.checkbox("EMA 21", value=True)
            show_ema50 = st.checkbox("EMA 50", value=True)
        with tog_col2:
            show_sma50 = st.checkbox("SMA 50", value=False)
            show_sma200 = st.checkbox("SMA 200", value=True)
        with tog_col3:
            show_rsi = st.checkbox("RSI (14)", value=True)
            show_macd = st.checkbox("MACD (12,26,9)", value=True)
            show_ichimoku = st.checkbox("Ichimoku Cloud (9-26-52)", value=True)

        # Nút tải / refresh — CHỈ KHI CLICK NÚT NÀY MỚI GỌI FETCH (lazy hoàn toàn)
        if st.button("📈 Tải / Cập nhật biểu đồ", type="primary", key="load_chart"):
            st.cache_data.clear()  # cho phép refresh thủ công
            st.session_state["chart_loaded"] = True

        # --- LAZY CHART DATA: chỉ fetch + vẽ sau khi user click nút ---
        selected_symbol = coin_symbol_map.get(selected_label, "BTC")

        if st.session_state.get("chart_loaded", False):
            with st.spinner("Đang tải dữ liệu..."):
                ohlc_df = fetch_daily_klines(selected_symbol, days=timeframe_days)

            if ohlc_df.empty or len(ohlc_df) < 10:
                st.error("Không đủ dữ liệu nến để vẽ biểu đồ. Vui lòng thử coin khác hoặc timeframe ngắn hơn.")
                show_strong_disclaimer()
            else:
                # Tính tất cả chỉ báo một lần (rẻ)
                close = ohlc_df["close"]
                ohlc_df = ohlc_df.copy()
                ohlc_df["EMA9"] = calculate_ema(close, 9)
                ohlc_df["EMA21"] = calculate_ema(close, 21)
                ohlc_df["EMA50"] = calculate_ema(close, 50)
                ohlc_df["SMA50"] = calculate_sma(close, 50)
                ohlc_df["SMA200"] = calculate_sma(close, 200)
                ohlc_df["RSI"] = calculate_rsi(ohlc_df, 14)
                ohlc_df["MACD"], ohlc_df["MACD_Signal"], ohlc_df["MACD_Hist"] = calculate_macd(ohlc_df)
                ohlc_df["Tenkan"], ohlc_df["Kijun"], ohlc_df["SenkouA"], ohlc_df["SenkouB"], ohlc_df["Chikou"] = \
                    calculate_ichimoku(ohlc_df)

                # --- XÂY DỰNG BIỂU ĐỒ PLOTLY (3 SUBPLOTS) ---
                fig = make_subplots(
                    rows=3, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.035,
                    row_heights=[0.58, 0.21, 0.21],
                    subplot_titles=(
                        f"{selected_label} — {timeframe_days} ngày (Daily OHLC + Chỉ báo)",
                        "RSI (14) — Quá mua >70 / Quá bán <30",
                        "MACD (12, 26, 9) + Histogram"
                    )
                )

                # Row 1: Candlestick
                fig.add_trace(
                    go.Candlestick(
                        x=ohlc_df.index,
                        open=ohlc_df["open"],
                        high=ohlc_df["high"],
                        low=ohlc_df["low"],
                        close=ohlc_df["close"],
                        name="OHLC",
                        increasing_line_color="#00ff9f",
                        decreasing_line_color="#ff5252"
                    ),
                    row=1, col=1
                )

                # EMA lines (nếu bật)
                if show_ema9:
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["EMA9"], name="EMA 9",
                                             line=dict(color="#00b0ff", width=1.5)), row=1, col=1)
                if show_ema21:
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["EMA21"], name="EMA 21",
                                             line=dict(color="#ff9800", width=1.5)), row=1, col=1)
                if show_ema50:
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["EMA50"], name="EMA 50",
                                             line=dict(color="#e040fb", width=1.5)), row=1, col=1)

                # SMA
                if show_sma50:
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["SMA50"], name="SMA 50",
                                             line=dict(color="#ffeb3b", width=1.2, dash="dash")), row=1, col=1)
                if show_sma200:
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["SMA200"], name="SMA 200",
                                             line=dict(color="#ff4081", width=2)), row=1, col=1)

                # Ichimoku Cloud + 5 đường (nếu bật)
                if show_ichimoku:
                    # Cloud fill (đơn giản, màu trong suốt đẹp)
                    fig.add_trace(go.Scatter(
                        x=ohlc_df.index, y=ohlc_df["SenkouA"],
                        line=dict(color="rgba(0,0,0,0)"), showlegend=False, hoverinfo="skip"
                    ), row=1, col=1)
                    fig.add_trace(go.Scatter(
                        x=ohlc_df.index, y=ohlc_df["SenkouB"],
                        fill="tonexty",
                        fillcolor="rgba(0, 200, 150, 0.18)",
                        line=dict(color="rgba(0,0,0,0)"),
                        name="Ichimoku Cloud",
                        showlegend=True
                    ), row=1, col=1)

                    # 5 đường Ichimoku
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["Tenkan"], name="Tenkan-sen (9)",
                                             line=dict(color="#ff5252", width=1.2)), row=1, col=1)
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["Kijun"], name="Kijun-sen (26)",
                                             line=dict(color="#2196f3", width=1.2)), row=1, col=1)
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["Chikou"], name="Chikou Span",
                                             line=dict(color="#9c27b0", width=1, dash="dot")), row=1, col=1)

                # Row 2: RSI
                if show_rsi and "RSI" in ohlc_df.columns:
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["RSI"], name="RSI 14",
                                             line=dict(color="#9c27b0", width=1.8)), row=2, col=1)
                    # Overbought / Oversold lines
                    fig.add_hline(y=70, line=dict(color="#ff5252", dash="dash", width=1), row=2, col=1)
                    fig.add_hline(y=30, line=dict(color="#00ff9f", dash="dash", width=1), row=2, col=1)
                    fig.add_hline(y=50, line=dict(color="#555", width=0.5), row=2, col=1)

                # Row 3: MACD
                if show_macd and "MACD" in ohlc_df.columns:
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["MACD"], name="MACD Line",
                                             line=dict(color="#00bcd4", width=1.6)), row=3, col=1)
                    fig.add_trace(go.Scatter(x=ohlc_df.index, y=ohlc_df["MACD_Signal"], name="Signal Line",
                                             line=dict(color="#ff9800", width=1.4)), row=3, col=1)

                    # Histogram màu xanh/đỏ
                    colors = np.where(ohlc_df["MACD_Hist"] >= 0, "#00ff9f", "#ff5252")
                    fig.add_trace(go.Bar(
                        x=ohlc_df.index, y=ohlc_df["MACD_Hist"], name="Histogram",
                        marker_color=colors, opacity=0.75
                    ), row=3, col=1)

                # Layout chung
                fig.update_layout(
                    height=820,
                    margin=dict(l=40, r=20, t=50, b=30),
                    legend=dict(orientation="h", y=1.02, x=0, font=dict(size=10)),
                    hovermode="x unified",
                    plot_bgcolor="#0e1117",
                    paper_bgcolor="#0e1117",
                    font=dict(color="#e0e0e0"),
                    xaxis_rangeslider_visible=False,
                    showlegend=True
                )
                fig.update_xaxes(gridcolor="#2a2d35", showspikes=True)
                fig.update_yaxes(gridcolor="#2a2d35")

                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})

                # --- BẢNG GIẢI THÍCH CHỈ BÁO (HỌC TẬP) ---
                st.subheader("📖 Giải thích các chỉ báo (dùng để học)")
                explanation_data = {
                    "Chỉ báo": [
                        "EMA 9 / 21 / 50",
                        "SMA 50 / 200",
                        "RSI (14)",
                        "MACD (12,26,9)",
                        "Ichimoku Cloud (9-26-52)"
                    ],
                    "Công thức / Ý nghĩa ngắn gọn": [
                        "Trung bình trượt hàm mũ — phản ứng nhanh với giá gần đây. EMA9 rất nhạy, dùng cho tín hiệu ngắn hạn.",
                        "Trung bình trượt đơn giản. SMA200 là đường xu hướng dài hạn quan trọng (Golden/Death cross với SMA50).",
                        "Chỉ báo động lượng. >70 = quá mua (cân nhắc chốt), <30 = quá bán. 50 = trung lập.",
                        "MACD Line = EMA12 - EMA26. Signal = EMA9(MACD). Histogram thể hiện sức mạnh. Cắt nhau = tín hiệu.",
                        "Hệ thống 5 đường + mây. Mây = hỗ trợ/kháng cự tương lai. Giá trên mây = xu hướng tăng mạnh."
                    ],
                    "Cách sử dụng phổ biến": [
                        "Giá > EMA9 + EMA9 > EMA21 → ngắn hạn bullish",
                        "SMA50 cắt lên SMA200 (Golden Cross) → xu hướng tăng dài hạn",
                        "RSI giảm từ trên 70 + phân kỳ → tín hiệu đảo chiều giảm",
                        "MACD cắt lên Signal + Histogram tăng → mua mạnh",
                        "Giá trên mây + Tenkan > Kijun + mây xanh → xu hướng tăng rất mạnh"
                    ]
                }
                st.dataframe(
                    pd.DataFrame(explanation_data),
                    hide_index=True,
                    use_container_width=True
                )

                st.caption("⚠️ Lưu ý: Dữ liệu nến 365 ngày từ Binance là daily → rất phù hợp tính SMA200 & Ichimoku. Timeframe ngắn hơn sẽ có ít nến hơn.")
                show_strong_disclaimer()
        else:
            st.info("📌 Nhấn nút **Tải / Cập nhật biểu đồ** bên trên để tải dữ liệu nến từ Binance và hiển thị biểu đồ kỹ thuật với đầy đủ chỉ báo (EMA, SMA, RSI, MACD, Ichimoku). Dữ liệu chỉ fetch khi bạn yêu cầu.")
            show_strong_disclaimer()

    # ==========================================================================
    # TAB 3: TIN TỨC KINH TẾ - TÀI CHÍNH VIỆT NAM (RSS) — HOÀN TOÀN LAZY
    # ==========================================================================
    with tab3:
        st.header("📰 Tin tức Kinh tế - Tài chính Việt Nam")
        st.caption("Nguồn: VNExpress • Tuổi Trẻ • CafeF • VnEconomy (RSS) • Cache 5 phút (ttl=300)")

        # Nút Làm mới — CHỈ KHI CLICK NÚT NÀY MỚI GỌI FETCH RSS (lazy, không chạm network ở startup)
        if st.button("🔄 Làm mới tin tức", type="primary", key="refresh_vn_news"):
            st.cache_data.clear()
            with st.spinner("Đang tải dữ liệu..."):
                news_articles = fetch_vietnam_econ_news(limit=12)
            st.session_state["tab3_news_loaded"] = True
            st.session_state["tab3_news_articles"] = news_articles

        # === RENDER: chỉ hiển thị sau khi user đã click nút ít nhất 1 lần ===
        if st.session_state.get("tab3_news_loaded", False):
            news_articles = st.session_state.get("tab3_news_articles", [])

            if news_articles:
                # THÀNH CÔNG: Hiển thị tối đa 12 bài mới nhất (giữ nguyên 100% logic hiển thị cũ)
                st.caption(f"Hiển thị {min(12, len(news_articles))} bài mới nhất • Cập nhật gần đây")

                for article in news_articles[:12]:
                    title = article.get("title", "Không có tiêu đề")
                    source = article.get("source", "Nguồn ẩn")
                    published_ts = article.get("published_ts", 0)
                    summary = article.get("summary", "")
                    url = article.get("url", "#")
                    time_str = get_time_ago_vn(published_ts)

                    with st.container(border=True):
                        st.markdown(f"### [{title}]({url})")
                        st.caption(f"📰 {source}  •  ⏱️ {time_str}")
                        if summary:
                            st.write(summary)
                        st.markdown(f"[Đọc bài đầy đủ →]({url})", unsafe_allow_html=True)

                st.divider()
                st.caption("💡 Tin tức chỉ mang tính tham khảo, không phải lời khuyên đầu tư tài chính.")
            else:
                # RSS fail tạm thời → friendly message
                st.warning("⚠️ Tạm thời không lấy được tin từ các nguồn RSS.")
                st.info("Các báo Việt Nam (VNExpress, Tuổi Trẻ, CafeF, VnEconomy) có thể đang bảo trì hoặc Cloud bị chặn tạm thời. Vui lòng nhấn **Làm mới tin tức** sau ít phút để thử lại.")
        else:
            st.info("📌 Nhấn nút **Làm mới tin tức** bên trên (sau khi chuyển sang tab này) để tải tin tức kinh tế - tài chính Việt Nam từ RSS. Dữ liệu chỉ fetch khi bạn yêu cầu — giúp app chạy ổn định trên Streamlit Community Cloud.")

        show_strong_disclaimer()

    # ==========================================================================
    # FOOTER GLOBAL (DISCLAIMER + THÔNG TIN)
    # ==========================================================================
    st.divider()
    st.markdown(
        "<div style='text-align:center; color:#888; font-size:0.82rem;'>"
        "Crypto Dashboard Pro v1.0 &nbsp;•&nbsp; Dữ liệu công khai &nbsp;•&nbsp; "
        "Chỉ để tham khảo &nbsp;•&nbsp; Không phải lời khuyên tài chính"
        "</div>",
        unsafe_allow_html=True
    )
    show_strong_disclaimer()


# Chạy app
if __name__ == "__main__":
    main()
