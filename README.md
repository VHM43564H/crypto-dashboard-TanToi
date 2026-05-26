# 📊 Crypto Dashboard Pro

**Ứng dụng phân tích tiền điện tử chuyên nghiệp** được xây dựng bằng **Streamlit** với đúng **3 tab**, giao diện tiếng Việt hiện đại và đầy đủ chỉ báo kỹ thuật.

> ⚠️ **TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM QUAN TRỌNG**  
> Ứng dụng này **chỉ mang tính tham khảo, giáo dục**. Không phải lời khuyên tài chính, đầu tư, giao dịch hay pháp lý. Giá crypto biến động cực mạnh — bạn có thể mất toàn bộ vốn. Luôn tự nghiên cứu kỹ (DYOR). Tác giả không chịu trách nhiệm về bất kỳ quyết định nào của bạn.

---

## ✨ Tính năng nổi bật

| Tab | Nội dung chính |
|-----|----------------|
| **1. Giá biến động Top 20 Coin** | Top 5 metric cards + bảng `st.dataframe` sortable đầy đủ (Rank, Coin, Giá, 24h%, 7d%, Volume, MC). Màu xanh/đỏ trực quan. Dữ liệu CoinGecko. |
| **2. Phân tích Kỹ thuật** | Chọn coin + timeframe (30-365 ngày). Biểu đồ nến Plotly tương tác + **đầy đủ chỉ báo**: EMA(9,21,50), SMA(50,200), RSI(14), MACD(12,26,9) + histogram, **Ichimoku Cloud chuẩn 9-26-52** (5 đường + mây). Tùy chọn bật/tắt từng chỉ báo. Bảng giải thích chi tiết bên dưới. |
| **3. Tin tức Crypto 24h** | 10-15 bài tin mới nhất từ CryptoCompare (miễn phí, không key). Tiêu đề link, nguồn, thời gian tương đối, tóm tắt ngắn. Nút làm mới. |

**Điểm kỹ thuật**:
- `@st.cache_data(ttl=...)` cho mọi API call → giảm rate limit, trải nghiệm nhanh.
- Tính chỉ báo **thủ công bằng pandas/numpy** (có comment giải thích công thức — rất tốt để học).
- Sử dụng **Binance Public klines** cho nến daily sạch (giải quyết vấn đề granularity thô của CoinGecko free /ohlc).
- Theme tối chuyên nghiệp + CSS tùy chỉnh.
- Disclaimer xuất hiện ở **mọi tab + footer**.

---

## 🚀 Cách chạy (Windows - PowerShell)

### 1. Tạo môi trường ảo (khuyến nghị mạnh)

```powershell
cd "C:\Users\ZBOOK G6\Documents\crypto-dashboard-pro"

python -m venv .venv
.venv\Scripts\activate
```

### 2. Cài đặt thư viện

```powershell
pip install -r requirements.txt
```

### 3. Chạy ứng dụng

```powershell
streamlit run app.py
```

Ứng dụng sẽ tự động mở trình duyệt tại **http://localhost:8501**

---

## 📁 Cấu trúc dự án

```
crypto-dashboard-pro/
├── app.py                 # Toàn bộ ứng dụng (logic + UI + comment học tập)
├── requirements.txt       # Danh sách package
├── README.md              # File này
├── PLAN.md                # Kế hoạch chi tiết triển khai (rất hữu ích để học)
└── .streamlit/
    └── config.toml        # Cấu hình theme tối crypto
```

---

## 🧠 Những điểm học tập quan trọng trong code (app.py)

1. **Hybrid Data Source**:
   - CoinGecko → metadata + top 20 + giá realtime
   - Binance → nến OHLC daily chính xác cho TA (không bị thô như CG free)
   - CryptoCompare → news

2. **Tính chỉ báo thủ công** (hàm `calculate_*`):
   - SMA/EMA đơn giản rolling + ewm
   - RSI: công thức Wilder chuẩn (gain/loss tách biệt)
   - MACD + histogram
   - Ichimoku đầy đủ (Tenkan, Kijun, Senkou A/B shift +26, Chikou shift -26)

3. **Plotly Subplots**:
   - 3 hàng: Price (candlestick + nhiều line + cloud fill) | RSI | MACD
   - `make_subplots(rows=3, shared_xaxes=True)`
   - Toggles điều khiển `fig.add_trace` có điều kiện

4. **Caching & UX**:
   - `st.cache_data.clear()` + `st.rerun()` khi nhấn nút Cập nhật
   - Spinner, warning, error rõ ràng

5. **Vietnamese-first UI** + professional dark theme.

---

## ⚠️ Lưu ý khi sử dụng / Phát triển tiếp

- **Rate limit**: CoinGecko free ~30-50 req/phút. Cache 5 phút + chỉ refresh khi cần.
- Một số coin rất nhỏ có thể không có cặp USDT trên Binance → app sẽ fallback (ít xảy ra với Top 20).
- Ichimoku / SMA200 cần đủ dữ liệu → 365 ngày là lựa chọn tốt nhất.
- Muốn mở rộng: thêm tab Portfolio, Bollinger, backtest đơn giản, lưu setting vào session_state.

---

## 📚 Nguồn dữ liệu

- [CoinGecko Public API](https://docs.coingecko.com/reference/coins-markets)
- [Binance API Klínes (public, no key)](https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data)
- [CryptoCompare News API](https://min-api.cryptocompare.com/)

---

## 📄 License & Disclaimer

Dự án này **chỉ dành cho mục đích học tập và tham khảo cá nhân**.

**KHÔNG** phải sản phẩm tài chính.  
Tác giả không chịu trách nhiệm về bất kỳ thiệt hại trực tiếp/gián tiếp nào phát sinh từ việc sử dụng ứng dụng.

---

**Phiên bản**: 1.0  
**Cập nhật**: Tháng 05/2026  
**Build với**: Streamlit + Plotly + Pandas (Python)

Chúc bạn học hỏi vui vẻ và trade an toàn! 📈
