# 📋 KẾ HOẠCH CHI TIẾT TRIỂN KHAI - Crypto Dashboard Pro

**Ngày lập kế hoạch**: 2026-05 (dựa trên yêu cầu người dùng)  
**Mục tiêu**: Xây dựng ứng dụng Streamlit chuyên nghiệp, sạch sẽ, có đúng **3 tab** sử dụng `st.tabs()`, giao diện tiếng Việt, disclaimer mạnh ở mọi nơi, học tập được (comment chi tiết).

---

## 1. Cấu trúc dự án (Project Structure)

```
crypto-dashboard-pro/
├── app.py                      # File chính DUY NHẤT chứa toàn bộ logic + UI (không tách module để đơn giản chạy 1 lệnh)
├── requirements.txt            # Danh sách package chính xác
├── README.md                   # Hướng dẫn chạy, giải thích nhanh, disclaimer
├── PLAN.md                     # File này - kế hoạch chi tiết (để tham khảo sau)
└── .streamlit/
    └── config.toml             # Cấu hình theme tối (dark) chuyên nghiệp cho crypto
```

**Lý do single-file app.py**: 
- Dễ deploy (Streamlit Cloud, local), dễ học.
- Tất cả logic nằm cùng chỗ, comment rõ ràng theo section.
- Phù hợp yêu cầu "viết comment rõ ràng trong code để học tập".

---

## 2. Tech Stack & Thư viện (chỉ những gì cần thiết)

| Package     | Phiên bản tối thiểu | Mục đích |
|-------------|---------------------|----------|
| streamlit   | >=1.32              | Framework web app, tabs, caching, widgets |
| pandas      | >=2.0               | Xử lý dữ liệu, tính chỉ báo TA |
| numpy       | >=1.26              | Hỗ trợ tính toán nhanh |
| plotly      | >=5.18              | Biểu đồ tương tác (candlestick + subplots + fill cloud) |
| requests    | >=2.31              | Gọi API CoinGecko, Binance, CryptoCompare |

**Không dùng**:
- `yfinance` (không nhất quán với top20 từ CG)
- `pandas-ta` / `ta-lib` (dùng tính thủ công để **học** công thức)
- `streamlit-extras`, `st-pages` (giữ đơn giản, chỉ st.tabs())

---

## 3. Nguồn dữ liệu (Data Sources) - Chiến lược Hybrid

### 3.1 Tab 1 & Metadata (CoinGecko Public API - hoàn toàn miễn phí, không key)
- Endpoint: `GET https://api.coingecko.com/api/v3/coins/markets`
- Params chính:
  - `vs_currency=usd`
  - `order=market_cap_desc`
  - `per_page=20&page=1`
  - `price_change_percentage=24h,7d`
  - `sparkline=false`
- Response fields dùng: `market_cap_rank`, `id`, `symbol`, `name`, `image`, `current_price`, `price_change_percentage_24h`, `price_change_percentage_7d`, `total_volume`, `market_cap`
- Rate limit free: ~30-50 calls/phút → **@st.cache_data(ttl=300)** là bắt buộc.

### 3.2 Tab 2 - Dữ liệu nến OHLC (Binance Public API - miễn phí, không key)
- Endpoint: `GET https://api.binance.com/api/v3/klines`
- Params: `symbol=BTCUSDT&interval=1d&limit=365`
- Lý do chọn Binance thay vì CoinGecko /ohlc:
  - CoinGecko free /ohlc cho >30 ngày chỉ trả về nến 4 ngày (quá thô, SMA200 không có đủ bar, RSI/MACD sai lệch).
  - Binance trả **daily OHLC sạch 100%** (1d interval), lên đến 1000 bar → 365 ngày hoàn hảo cho mọi chỉ báo.
  - Hầu hết Top 20 coin đều có cặp XXXUSDT.
- Fallback: nếu symbol không tồn tại trên Binance → dùng CoinGecko /ohlc (và cảnh báo).
- Symbol mapping: `f"{coin_symbol.upper()}USDT"` (hầu như luôn đúng).

### 3.3 Tab 3 - Tin tức (CryptoCompare Free News API)
- Endpoint: `GET https://min-api.cryptocompare.com/data/v2/news/?lang=EN`
- Không cần key cho usage cơ bản.
- Response: `Data[]` với `title`, `source_info.name`, `body`, `url`, `published_on` (unix seconds), `imageurl`.
- Lấy 12-15 bài mới nhất, sort latest.
- Tính "time ago" thủ công (không cần thư viện bên ngoài).

**Lý do không dùng CoinGecko News**: Endpoint /news của CG không phải core public ổn định cho mọi người; CryptoCompare ổn định và phổ biến cho demo.

---

## 4. Chiến lược Caching & Refresh (@st.cache_data)

```python
@st.cache_data(ttl=300)  # 5 phút
def fetch_top_coins():
    ...

@st.cache_data(ttl=600)  # 10 phút cho nến (dữ liệu lịch sử ít thay đổi)
def fetch_daily_klines(binance_symbol: str, days: int):
    ...

@st.cache_data(ttl=300)
def fetch_crypto_news(limit: int = 15):
    ...
```

**Nút "Cập nhật dữ liệu" / "Làm mới"**:
- `if st.button("Cập nhật dữ liệu", type="primary"):`
  - `st.cache_data.clear()`
  - `st.rerun()`
- Hiển thị "Dữ liệu cache đến: ..." hoặc dùng `last_updated` từ API.
- Ưu điểm: UX mượt, giảm rate limit, user vẫn chủ động refresh.

---

## 5. Chi tiết 3 Tab (Yêu cầu chính xác)

### Tab 1: Giá biến động Top 20 Coin
- Fetch 1 lần (cache) → dùng chung cho Tab 1 + dropdown Tab 2.
- Layout:
  1. Header + nút Cập nhật + disclaimer nhỏ.
  2. **Top 5 metric cards** (st.columns(5)):
     - st.metric(label="#1 Bitcoin (BTC)", value="$67,123.45", delta="2.34%", delta_color="normal")
     - Có thể thêm nhỏ logo (st.image với width=28) hoặc emoji.
  3. **Full sortable st.dataframe**:
     - Columns (tiếng Việt): Hạng | Coin | Giá (USD) | 24h % | 7d % | Volume 24h | Market Cap
     - `column_config`:
       - NumberColumn format "$%.2f", "$,.0f" cho volume/MC
       - % format "%.2f%%"
     - Một cột "Xu hướng 24h" dạng text có emoji 🟢 / 🔴 để trực quan (dù sort lexical).
  4. Footer disclaimer mạnh.

### Tab 2: Phân tích Kỹ thuật
- Controls (trên biểu đồ):
  - `st.selectbox` chọn coin từ Top 20 (hiển thị "Bitcoin (BTC)", value lưu id + symbol).
  - Timeframe: `st.segmented_control` hoặc `st.radio` / `st.selectbox` : 30 / 90 / 180 / 365 ngày (mặc định 90).
  - Nút "Tải biểu đồ" hoặc auto rerun khi thay đổi widget.
- **Toggles chỉ báo** (dùng `st.columns(3)` + checkbox):
  - Nhóm 1: EMA 9 / EMA 21 / EMA 50 (mặc định bật)
  - Nhóm 2: SMA 50 / SMA 200
  - Nhóm 3: RSI (14) | MACD (12,26,9) | Ichimoku Cloud (9-26-52) (mặc định bật hết)
- **Biểu đồ Plotly chính (make_subplots, rows=3)**:
  - Row 1 (60-65%): Candlestick + EMA/SMA lines + **Toàn bộ Ichimoku** (Tenkan, Kijun, Chikou, Senkou A, Senkou B + fill cloud)
  - Row 2 (18%): RSI line + 2 đường hline 30/70 (đỏ/xanh)
  - Row 3 (17%): MACD line + Signal line + Histogram (Bar xanh/đỏ theo sign)
  - Layout: `hovermode="x unified"`, legend ngang, height ~820, xaxis rangslider=False, title động theo coin + timeframe.
- **Dưới biểu đồ**: Bảng giải thích (st.dataframe hoặc markdown table + bullet):
  - Tên chỉ báo + tham số
  - Công thức ngắn gọn (có thể copy code comment)
  - Cách đọc phổ biến (VD: "RSI > 70 → quá mua, cân nhắc chốt lời")
- Xử lý NaN: các chỉ báo dài (SMA200, Ichimoku 52+26) sẽ có khoảng đầu NaN → Plotly tự bỏ qua.

### Tab 3: Tin tức Crypto 24h
- Fetch 15 bài → hiển thị 10-12 bài.
- Mỗi bài là một `st.container(border=True)` hoặc expander:
  - Tiêu đề là markdown link: `[Tiêu đề bài viết](https://...)`
  - Dòng nhỏ: `Nguồn: CryptoPotato • 42 phút trước`
  - Tóm tắt ngắn: `body[:300] + "..."` (loại bỏ HTML nếu có)
  - (Optional) thumbnail nhỏ bên phải nếu muốn.
- Nút "🔄 Làm mới tin tức" → clear cache news + rerun.
- Sắp xếp: mới nhất trước (theo published_on).

---

## 6. Công thức chỉ báo (Triển khai thủ công - Educational)

Tất cả hàm đều nhận `pd.DataFrame` có cột `['open','high','low','close']` (index datetime hoặc range).

```python
# SMA / EMA
sma = close.rolling(period).mean()
ema = close.ewm(span=period, adjust=False).mean()

# RSI 14 chuẩn Wilder
delta = close.diff()
gain = delta.where(delta>0, 0).rolling(14).mean()
loss = (-delta.where(delta<0, 0)).rolling(14).mean()
rsi = 100 - (100 / (1 + gain/loss))

# MACD
macd = ema12 - ema26
signal = macd.ewm(9).mean()
hist = macd - signal

# ICHIMOKU đầy đủ (9,26,52, displacement=26)
tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
kijun  = (high.rolling(26).max() + low.rolling(26).min()) / 2
senkou_a = ((tenkan + kijun) / 2).shift(26)
senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
chikou = close.shift(-26)
```

**Lý do thủ công**:
- Người học thấy rõ công thức (không black-box).
- Không thêm dependency nặng, dễ cài trên Windows.
- Comment từng dòng trong code.

---

## 7. Giao diện & Polish (Professional UI)

- **Theme**: Dark crypto (xanh neon + xám đậm) qua `.streamlit/config.toml`
  - primaryColor = "#00ff9f" (màu lãi)
  - background = "#0e1117"
- **Custom CSS** (unsafe_allow_html):
  - Làm đẹp metric cards (border, shadow nhẹ)
  - Dataframe header font
  - Link màu accent
  - Disclaimer box vàng/cam rõ ràng
- **Layout rộng** (`layout="wide"`)
- **Icon + Emoji** nhất quán: 📊 📉 📰 📈 🟢 🔴 ⚠️
- **Loading**: `st.spinner("Đang tải dữ liệu từ CoinGecko...")` quanh fetch (dù cache thường nhanh)
- **Error**: `st.error(...)` + gợi ý "thử nút Cập nhật" hoặc kiểm tra mạng.
- **Responsive**: columns tự wrap trên mobile.

---

## 8. Vị trí Disclaimer (Bắt buộc mạnh)

- **Mọi tab**: 
  - Dưới header tab (st.info hoặc st.warning)
  - Hoặc trong `st.expander("⚠️ Lưu ý quan trọng - Đọc trước khi sử dụng")`
  - Dưới cùng tab trước footer
- **Footer toàn app**: st.caption hoặc markdown nhỏ, lặp lại câu:
  > "Ứng dụng này chỉ mang tính tham khảo. Không phải lời khuyên tài chính, đầu tư hay pháp lý."

- **Nội dung mẫu** (dịch + mạnh):
  "Dữ liệu chỉ mang tính tham khảo. Giá tiền điện tử biến động mạnh, bạn có thể mất toàn bộ số vốn đầu tư. Không phải tư vấn tài chính. Tác giả và nguồn dữ liệu không chịu trách nhiệm về quyết định giao dịch của bạn. Luôn tự nghiên cứu kỹ (DYOR)."

---

## 9. Xử lý Edge Cases & Rate Limit

1. API fail / timeout / 429 → return empty DF + st.warning + nút retry rõ.
2. Coin không có trên Binance → thử CoinGecko ohlc + cảnh báo "Dữ liệu nến thô (granularity thấp)".
3. Timeframe 365d + SMA200 → một số NaN đầu biểu đồ (bình thường, Plotly bỏ qua).
4. Ichimoku trên <52+26 bars → cloud và Chikou có ít điểm → vẫn vẽ những gì có.
5. News body có ký tự đặc biệt → escape an toàn.
6. Windows path → dùng raw string hoặc pathlib (nhưng không cần vì single file).

---

## 10. Quy trình triển khai (Step-by-step thực tế)

1. Tạo thư mục + .streamlit/config.toml (theme)
2. Viết requirements.txt (pin phiên bản lỏng)
3. Viết README.md (hướng dẫn venv + chạy trên Windows)
4. Viết app.py theo cấu trúc:
   a. Imports + page_config + custom_css
   b. Các hàm helper (format, time_ago, calculate_*)
   c. 3 hàm @st.cache_data fetch
   d. Hàm show_disclaimer()
   e. Main: title, top_coins_df = fetch...
   f. tabs = st.tabs([...])
   g. Tab1 code (top5 cols + dataframe)
   h. Tab2 code (select + timeframe + toggles + build_fig + plot + explanation)
   i. Tab3 code (news list + refresh)
   j. Footer global
5. Test local: `streamlit run app.py`
6. Thêm comment học tập ở mọi hàm quan trọng
7. (Optional) Chụp screenshot demo → đưa vào README sau

---

## 11. Mở rộng sau này (không nằm trong scope hiện tại)

- Thêm tab Portfolio (nhập số lượng, tính PnL)
- Lưu indicator params vào session_state
- Thêm Bollinger Bands, Fibonacci
- Export chart PNG / CSV data
- Dark/light toggle
- Deploy Streamlit Community Cloud + GitHub

---

## 12. Rủi ro & Giảm thiểu

- **Rate limit CoinGecko**: Cache 5-10 phút + chỉ fetch khi user nhấn nút.
- **Binance symbol miss**: Fallback + log rõ trong UI.
- **Plotly quá nặng**: Giới hạn số trace (tối đa ~12-15 traces), height hợp lý.
- **Ichimoku fill đẹp**: Dùng 1 màu cloud bán trong suốt + giải thích rõ trong bảng (không dynamic color từng đoạn để giữ code ngắn gọn).

---

**Kết luận kế hoạch**: Thiết kế này đáp ứng 100% yêu cầu người dùng (3 tabs, st.tabs, top20 CG, đầy đủ chỉ báo + toggle, news public API, disclaimer mạnh, cache, comment học, chạy `streamlit run app.py`).

File app.py sẽ được viết ngay sau khi plan này được chấp nhận (hoặc song song nếu user đồng ý).

---
*Plan này được tạo tự động từ phân tích yêu cầu + research API chính thức (tháng 05/2026).*
