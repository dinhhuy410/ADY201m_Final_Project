# ADY201m_Final_Project: AI Quant Investment Decision Support Platform

Dự án xây dựng **Ứng dụng Web Dashboard** phân tích và dự báo cổ phiếu Việt Nam, ứng dụng Deep Learning (LSTM, TCN, XGBoost) để dự báo giá đóng cửa và tự động hóa tín hiệu giao dịch.

**Cổ phiếu trọng tâm:** VCB (Ngân hàng TMCP Ngoại thương Việt Nam) — vốn hóa lớn nhất HOSE, tác động mạnh nhất đến VN-Index.

---

## I. Thông tin

| Môn học | ADY201m - Introduction to Data Science |
|---------|----------------------------------------|
| Giảng viên | Bùi Thị Loan |
| Lớp | AI2011 |

## II. Thành viên nhóm

| STT | Họ và Tên | MSSV | Vai trò |
|:---:|:---|:---|:---|
| 1 | Lưu Đình Huy | HE200075 | Leader |
| 2 | Trần Vũ Bình | HE200038 | Member |
| 3 | Quách Thiện Nhân | HE210429 | Member |

## III. Cấu trúc thư mục

```text
ADYFinal/
├── App.py                    # Streamlit application chính
├── database.py               # Module kết nối SQL Server
├── import_data.py            # Script import dữ liệu → SQL Server
├── requirements.txt          # Python dependencies
├── README.md                 # File này
├── README_SETUP.md           # Hướng dẫn cài đặt chi tiết
│
├── configs/
│   └── garch_config.txt      # Cấu hình GARCH volatility
│
├── data/
│   ├── VCB_data.csv          # Dữ liệu VCB (export từ SQL Server)
│   └── trade_history.csv     # Nhật ký giao dịch
│
├── models/                   # Trained models (cần train lại hoặc tải về)
│   ├── scaler.pkl            # StandardScaler
│   ├── vcb_xgb_model.pkl     # XGBoost model
│   ├── vcb_lstm_model.h5     # LSTM model
│   └── vcb_tcn_model.h5      # TCN model
│
└── notebooks/                # Jupyter notebooks
    ├── create_database.sql   # SQL script tạo bảng
    ├── Getdata.ipynb         # Thu thập dữ liệu
    ├── eda_vcb.ipynb         # Exploratory Data Analysis
    ├── Predict.ipynb         # Dự báo
    ├── Statistical_Tests.ipynb
    ├── Training_LSTM.ipynb
    ├── Training_XGBoost.ipynb
    └── Training TCN.ipynb
```

---

## IV. Cài đặt & Chạy

### Yêu cầu hệ thống
- **Microsoft SQL Server 2019+** (Express hoặc Developer)
- **ODBC Driver 17 for SQL Server**
- **Python 3.10+**

### Bước 1: Clone project
```bash
git clone https://github.com/dinhhuy410/ADY201m_Final_Project.git
cd ADY201m_Final_Project
```

### Bước 2: Tạo môi trường ảo
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Bước 3: Cài đặt packages
```bash
pip install -r requirements.txt
```

### Bước 4: Đảm bảo SQL Server đang chạy
```powershell
Get-Service -Name '*SQL*'
```

### Bước 5: Import dữ liệu vào SQL Server
```bash
python import_data.py
```
Script sẽ tự động:
1. Tạo database `ADY_QuantDB`
2. Tạo các bảng (COMPANIES, DAILY_STOCK_PRICES, TECHNICAL_INDICATORS)
3. Download dữ liệu VCB từ yfinance
4. Tính Technical Indicators
5. Export VCB_data.csv

### Bước 6: Chạy ứng dụng
```bash
streamlit run App.py
```

---

## V. Database Schema

### COMPANIES
| Cột | Kiểu | Mô tả |
|-----|------|-------|
| Ticker | VARCHAR(10) PK | Mã cổ phiếu |
| CompanyName | NVARCHAR(255) | Tên công ty |
| Industry | NVARCHAR(100) | Ngành |

### DAILY_STOCK_PRICES
| Cột | Kiểu | Mô tả |
|-----|------|-------|
| PriceID | INT IDENTITY PK | Khóa chính tự tăng |
| Ticker | VARCHAR(10) FK | Khóa ngoại → COMPANIES |
| TradingDate | DATE | Ngày giao dịch |
| OpenPrice | FLOAT | Giá mở cửa |
| HighPrice | FLOAT | Giá cao nhất |
| LowPrice | FLOAT | Giá thấp nhất |
| ClosePrice | FLOAT | Giá đóng cửa |
| Volume | BIGINT | Khối lượng |

### TECHNICAL_INDICATORS
| Cột | Kiểu | Mô tả |
|-----|------|-------|
| IndicatorID | INT IDENTITY PK | Khóa chính tự tăng |
| PriceID | INT UNIQUE FK | Khóa ngoại → DAILY_STOCK_PRICES |
| MA10, MA20, MA50 | FLOAT | Trung bình động |
| RSI | FLOAT | Chỉ số sức mạnh tương đối |
| MACD | FLOAT | Moving Average Convergence Divergence |
| BollingerUpper, BollingerLower | FLOAT | Dải Bollinger Bands |
| TradingSignal | VARCHAR(10) | BUY / SELL / HOLD |

---

## VI. Machine Learning Models

| Model | Framework | Mục đích |
|-------|-----------|----------|
| XGBoost | xgboost (vcb_xgb_model.pkl, load qua joblib) | Dự báo % thay đổi giá dựa trên đặc trưng kỹ thuật tabular — mạnh về nắm bắt phi tuyến giữa nhiều biến |
| LSTM | tensorflow.keras (vcb_lstm_model.h5) | Học mẫu hình chuỗi thời gian dài hạn (long-term dependencies) trong dữ liệu giá |
| TCN | tensorflow.keras (vcb_tcn_model.h5) | Bắt mẫu hình cục bộ/ngắn hạn qua tích chập theo thời gian, huấn luyện nhanh & ổn định hơn LSTM |
| Ensemble | Custom | Kết hợp 3 model (XGB 40%, LSTM 30%, TCN 30%) |

---

## VII. Technical Indicators

- **RSI(14)** — Relative Strength Index
- **MA10/MA20/MA50** — Simple Moving Averages
- **MACD** — Moving Average Convergence Divergence
- **Bollinger Bands(20,2)** — Độ biến động giá
- **ATR(14)** — Average True Range
- **ADX(14)** — Average Directional Index
- **EMA20/EMA50** — Exponential Moving Averages
- **VWAP** — Volume Weighted Average Price

---

## VIII. Quant Decision Engine
## Bảng tổng hợp hệ thống chấm điểm
| # | Yếu tố                               | Nguồn dữ liệu                      | Điều kiện chấm điểm                                                          | Điểm | Tối đa |
| - | ------------------------------------ | ---------------------------------- | ---------------------------------------------------------------------------- | ---: | -----: |
| 1 | **Xu hướng (Trend)**                 | EMA20, EMA50, SMA200               | EMA20 > EMA50                                                                |  +15 |     25 |
|   |                                      |                                    | Close > SMA200                                                               |  +10 |        |
| 2 | **Đồng thuận mô hình (Consensus)**   | Dự báo XGBoost, TCN, LSTM          | CV giữa 3 dự báo càng thấp → điểm càng cao: `20 − CV × 1000` (giới hạn 0–20) | 0–20 |     20 |
| 3 | **Động lượng (Momentum)**            | RSI, MACD                          | 45 ≤ RSI ≤ 65                                                                |   +7 |     15 |
|   |                                      |                                    | RSI > 65                                                                     |  +10 |        |
|   |                                      |                                    | MACD > MACD Signal                                                           |   +5 |        |
| 4 | **An toàn rủi ro (Risk)**            | GARCH volatility (dự báo ngày mai) | Vol < 25%                                                                    |  +20 |     20 |
|   |                                      |                                    | 25% ≤ Vol < 40%                                                              |  +12 |        |
|   |                                      |                                    | Vol ≥ 40%                                                                    |   +5 |        |
| 5 | **Thanh khoản (Volume)**             | Vol_Ratio (KL hôm nay / MA20)      | `min(10, Vol_Ratio × 5)`                                                     | 0–10 |     10 |
| 6 | **Sức mạnh giá (RSI vùng hồi phục)** | RSI                                | 30 < RSI < 40                                                                |  +10 |     10 |
|   |                                      |                                    | Ngoài vùng trên                                                              |   +5 |        |

### Tổng điểm (thang điểm 100)
```text
Tổng điểm = Trend + Consensus + Momentum + Risk + Volume + RSI
```
---
## Ánh xạ điểm → Khuyến nghị
| Khoảng điểm | Khuyến nghị  | Màu          | Sao   |
| ----------- | ------------ | ------------ | ----- |
| ≥ 85        | **MUA MẠNH** | 🟢 `#00e676` | ★★★★★ |
| 70 – 84     | **MUA**      | 🟢 `#a5d6a7` | ★★★★☆ |
| 45 – 69     | **NẮM GIỮ**  | 🟡 `#ffd700` | ★★★☆☆ |
| 25 – 44     | **BÁN**      | 🔴 `#ff8a80` | ★★☆☆☆ |
| < 25        | **BÁN MẠNH** | 🔴 `#ff5252` | ★☆☆☆☆ |
---
## Lớp cảnh báo bổ sung
Lớp cảnh báo này nằm **ngoài tổng điểm 100** và không làm thay đổi trực tiếp điểm Quant Decision Engine.
| Điều kiện             | Nguồn                                  | Hành động                                                                                     |
| --------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------- |
| `ci_width_pct > 6.0%` | Mô hình GARCH(1,1), khoảng tin cậy 95% | Hiển thị cảnh báo rủi ro cao, khuyến nghị **không mở vị thế mới** trong chu kỳ T+2.5 hiện tại |
---
## IX. Configuration

Môi trường kết nối SQL Server có thể cấu hình qua environment variables:

```powershell
$env:ADY_SQL_SERVER = "localhost"
$env:ADY_SQL_DATABASE = "ADY_QuantDB"
$env:ADY_SQL_TRUSTED = "yes"
```

Hoặc chỉnh trực tiếp trong file `database.py`.

---

## X. License

Dự án phục vụ mục đích học tập — môn ADY201m, Đại học FPT.
