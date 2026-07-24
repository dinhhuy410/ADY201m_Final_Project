# ADY201m_Final_Project: AI Quant Investment Decision Support Platform

Dự án xây dựng **Ứng dụng Web Dashboard** phân tích và dự báo cổ phiếu Việt Nam, ứng dụng Deep Learning (LSTM, TCN, XGBoost) để dự báo giá đóng cửa và tự động hóa tín hiệu giao dịch.

**Cổ phiếu trọng tâm:** VCB (Ngân hàng TMCP Ngoại thương Việt Nam) — vốn hóa lớn nhất HOSE, tác động mạnh nhất đến VN-Index.

---

## 📋 Thông tin

| Môn học | ADY201m - Introduction to Data Science |
|---------|----------------------------------------|
| Giảng viên | Bùi Thị Loan |
| Lớp | [Điền lớp] |

## 👥 Thành viên nhóm

| STT | Họ và Tên | MSSV | Vai trò |
|:---:|:---|:---|:---|
| 1 | Lưu Đình Huy | HE200075 | Leader |
| 2 | Trần Vũ Bình | HE200038 | Member |
| 3 | Quách Thiện Nhân | HE210429 | Member |

---

## 🏗️ Kiến trúc

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  yfinance API   │────▶│  Microsoft SQL   │────▶│  Streamlit   │
│  (Realtime data)│     │  Server          │     │  App.py      │
└─────────────────┘     │  (ADY_QuantDB)   │     └──────────────┘
                        └──────────────────┘            │
                              │                         ▼
                        ┌──────────────┐     ┌──────────────────┐
                        │  Model Layer │◀────│  Feature Engine  │
                        │  LSTM/TCN/   │     │  TA indicators   │
                        │  XGBoost     │     └──────────────────┘
                        └──────────────┘
                              │
                              ▼
                        ┌──────────────────┐
                        │  Quant Decision  │
                        │  Engine + Backtest│
                        └──────────────────┘
```

---

## 📁 Cấu trúc thư mục

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

## 🚀 Cài đặt & Chạy

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

## 📊 Database Schema

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

## 🤖 Machine Learning Models

| Model | Framework | Mục đích |
|-------|-----------|----------|
| XGBoost | scikit-learn | Dự báo giá đóng cửa |
| LSTM | TensorFlow/Keras | Dự báo chuỗi thời gian |
| TCN | PyTorch | Temporal Convolutional Network |
| Ensemble | Custom | Kết hợp 3 model (XGB 40%, LSTM 30%, TCN 30%) |

---

## ⚙️ Technical Indicators

- **RSI(14)** — Relative Strength Index
- **MA10/MA20/MA50** — Simple Moving Averages
- **MACD** — Moving Average Convergence Divergence
- **Bollinger Bands(20,2)** — Độ biến động giá
- **ATR(14)** — Average True Range
- **ADX(14)** — Average Directional Index
- **EMA20/EMA50** — Exponential Moving Averages
- **VWAP** — Volume Weighted Average Price

---

## 📈 Quant Decision Engine

Hệ thống ra quyết định dựa trên:
1. **AI Consensus Score** — Đồng thuận 3 model
2. **Technical Signals** — RSI, MACD, Bollinger Bands
3. **Market Regime Detection** — Trending vs Sideways
4. **Risk Parameters** — GARCH Volatility, Max Drawdown
5. **Position Sizing** — Kelly Criterion + ATR-based Stop Loss

---

## 🔧 Configuration

Môi trường kết nối SQL Server có thể cấu hình qua environment variables:

```powershell
$env:ADY_SQL_SERVER = "localhost"
$env:ADY_SQL_DATABASE = "ADY_QuantDB"
$env:ADY_SQL_TRUSTED = "yes"
```

Hoặc chỉnh trực tiếp trong file `database.py`.

---

## 📝 License

Dự án phục vụ mục đích học tập — môn ADY201m, Đại học [Tên trường].
