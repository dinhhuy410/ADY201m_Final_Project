# ADY_QuantDB — Hướng dẫn thiết lập và chạy project chi tiết

## Tổng quan

Project chuyển đổi từ đọc dữ liệu CSV sang **Microsoft SQL Server**.
- **BEFORE:** CSV → Python → Data Processing → Model → Output
- **AFTER:** SQL Server → Python → Data Processing → Model → Output

## Cấu trúc project

```
D:\AdyFinal\
├── App.py                    # Streamlit app (KHÔNG sửa — dùng yfinance realtime)
├── database.py               # Module kết nối SQL Server + load_data
├── import_data.py            # Script import dữ liệu từ yfinance → SQL Server
├── requirements.txt          # Dependencies
├── configs/
│   └── garch_config.txt
├── data/
│   ├── VCB_data.csv          # Export từ SQL Server (verify)
│   ├── hybrid_predictions_output.csv
│   ├── trade_history.csv     # Nhật ký giao dịch (rỗng)
│   └── vcb_stock.db          # SQLite backup (giữ nguyên, không dùng)
├── models/
│   ├── scaler.pkl
│   ├── vcb_lstm_model.h5
│   ├── vcb_tcn_model.h5
│   └── vcb_xgb_model.pkl
└── notebooks/
    ├── create_database.sql   # SQL script tạo bảng
    ├── Getdata.ipynb
    ├── Predict.ipynb
    └── ...
```

---

## YÊU CẦU HỆ THỐNG

1. **Microsoft SQL Server 2019+** (Express hoặc Developer)
2. **ODBC Driver 17 for SQL Server**
3. **Python 3.10+** với các packages trong `requirements.txt`

---

## CÀI ĐẶT TỪ ĐẦU

### Bước 1: Cài SQL Server

1. Tải SQL Server Express: https://www.microsoft.com/en-us/sql-server/sql-server-downloads
2. Chọn **Basic** → Install
3. Authentication: **Windows Authentication** (hoặc Mixed Mode nếu muốn dùng sa)
4. Nhớ tên server (thường là `localhost` hoặc `localhost\SQLEXPRESS`)

### Bước 2: Kiểm tra SQL Server đang chạy

```powershell
Get-Service -Name '*SQL*'
```

Phải có `MSSQLSERVER` hoặc `MSSQL$SQLEXPRESS` ở trạng thái **Running**.

### Bước 3: Cài ODBC Driver 17

Tải tại: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

Hoặc kiểm tra đã có chưa:
```powershell
Get-OdbcDriver -Name "*SQL Server*"
```

### Bước 4: Cài Python packages

```bash
cd D:\AdyFinal
pip install -r requirements.txt
pip install pyodbc
```

### Bước 5: Tạo database và import dữ liệu

```bash
python import_data.py
```

Script sẽ tự động:
1. Tạo database `ADY_QuantDB`
2. Tạo 3 bảng: COMPANIES, DAILY_STOCK_PRICES, TECHNICAL_INDICATORS
3. Download dữ liệu VCB từ yfinance (2020→2026)
4. Tính Technical Indicators (RSI, MA10/20/50, MACD, Bollinger)
5. Insert vào SQL Server
6. Export VCB_data.csv từ DB để verify

### Bước 6: Chạy ứng dụng

```bash
streamlit run App.py
```

---

## KIỂM TRA DỮ LIỆU

Sau khi import, verify bằng cách mở SQL Server Management Studio (SSMS):

```sql
USE ADY_QuantDB;

-- Kiểm tra số lượng bản ghi
SELECT COUNT(*) AS TotalPrices FROM dbo.DAILY_STOCK_PRICES;
SELECT COUNT(*) AS TotalIndicators FROM dbo.TECHNICAL_INDICATORS;
SELECT COUNT(*) AS TotalCompanies FROM dbo.COMPANIES;

-- Xem mẫu dữ liệu
SELECT TOP 5 * FROM dbo.DAILY_STOCK_PRICES WHERE Ticker = 'VCB' ORDER BY TradingDate DESC;
SELECT TOP 5 * FROM dbo.TECHNICAL_INDICATORS ORDER BY IndicatorID DESC;

-- Phân phối Trading Signals
SELECT TradingSignal, COUNT(*) AS Count
FROM dbo.TECHNICAL_INDICATORS
GROUP BY TradingSignal;

-- So sánh với CSV
SELECT * INTO #TempCSV FROM OPENROWSET(
    BULK 'D:\AdyFinal\data\VCB_data.csv',
    FORMATFILE = 'D:\AdyFinal\data\format.fmt',
    FIRSTROW = 2
);
```

Hoặc dùng Python:

```python
from database import verify_data_integrity
results = verify_data_integrity()
for key, value in results.items():
    print(f"{key}: {value}")
```

---

## CẤU HÌNH KẾT NỐI

Mặc định kết nối đến `localhost` với Windows Authentication.

Để thay đổi, đặt environment variables:

```bash
# Windows PowerShell
$env:ADY_SQL_SERVER = "localhost\\SQLEXPRESS"
$env:ADY_SQL_DATABASE = "ADY_QuantDB"
$env:ADY_SQL_TRUSTED = "yes"

# Hoặc dùng username/password
$env:ADY_SQL_USER = "sa"
$env:ADY_SQL_PASSWORD = "your_password"
$env:ADY_SQL_TRUSTED = "no"
```

---

## XỬ LÝ LỖI

### Lỗi: "Login failed for user"

- Kiểm tra SQL Server authentication mode
- Nếu dùng Windows Auth: đảm bảo user hiện tại có quyền
- Nếu dùng SQL Auth: kiểm tra username/password trong `database.py`

### Lỗi: "ODBC Driver not found"

- Cài ODBC Driver 17 cho SQL Server
- Hoặc đổi DRIVER trong CONNECTION_STRING thành driver khác

### Lỗi: "Database already exists"

- Database đã tồn tại, chỉ cần chạy lại `import_data.py`
- Hoặc xóa database cũ trong SSMS rồi chạy lại

### Lỗi: "Cannot open database"

- Đảm bảo SQL Server đang chạy
- Kiểm tra firewall cho port 1433

---

## RESET DATABASE

Nếu muốn xóa toàn bộ dữ liệu và import lại:

```python
# Chạy reset_database.py (tự tạo)
import pyodbc
from database import CONNECTION_STRING

conn = pyodbc.connect(CONNECTION_STRING)
cursor = conn.cursor()
cursor.execute("DELETE FROM [dbo].[TECHNICAL_INDICATORS]")
cursor.execute("DELETE FROM [dbo].[DAILY_STOCK_PRICES]")
cursor.execute("DELETE FROM [dbo].[COMPANIES]")
conn.commit()
conn.close()

# Sau đó chạy lại import
# python import_data.py
```

---

## LƯU Ý QUAN TRỌNG

1. **App.py KHÔNG cần sửa** — nó dùng yfinance realtime, không đọc CSV
2. **Notebooks vẫn đọc VCB_data.csv** — file này được export từ SQL Server, format giống hệt
3. **Models đã train sẵn** — không cần retrain khi chuyển sang SQL
4. **trade_history.csv rỗng** — có thể migrate sang bảng TRADE_LOG trong tương lai
5. **Chỉ VCB** — dự án chỉ import dữ liệu VCB, các ticker khác (HPG, FPT...) chưa có trong SQL
