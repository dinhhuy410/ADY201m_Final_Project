"""
database.py — Module kết nối và truy vấn Microsoft SQL Server cho ADY_QuantDB.
- Kết nối SQL Server qua pyodbc hoặc SQLAlchemy
- Load dữ liệu VCB giống hệt format VCB_data.csv
- Load dữ liệu lịch sử giao dịch (trade_history)
- Hàm helper cho toàn bộ project
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

# ============================================================
# CẤU HÌNH KẾT NỐI SQL SERVER
# ============================================================
SQL_SERVER = os.environ.get("ADY_SQL_SERVER", "localhost")
SQL_DATABASE = os.environ.get("ADY_SQL_DATABASE", "ADY_QuantDB")
SQL_TRUSTED = os.environ.get("ADY_SQL_TRUSTED", "yes").lower() == "yes"

# Connection string cho pyodbc — connect vào MASTER trước
MASTER_CONNECTION_STRING = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE=master;"
    f"Trusted_Connection=yes;"
)

# Connection string cho ADY_QuantDB
if SQL_TRUSTED:
    CONNECTION_STRING = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"Trusted_Connection=yes;"
    )
else:
    SQL_USER = os.environ.get("ADY_SQL_USER", "sa")
    SQL_PASSWORD = os.environ.get("ADY_SQL_PASSWORD", "")
    CONNECTION_STRING = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};"
        f"PWD={SQL_PASSWORD};"
    )


def get_connection():
    """
    Tạo kết nối pyodbc đến SQL Server (ADY_QuantDB).
    
    Returns:
        pyodbc.Connection — kết nối mở
    """
    import pyodbc
    
    conn = pyodbc.connect(CONNECTION_STRING)
    return conn


def get_master_connection():
    """Tạo kết nối đến MASTER database (để tạo database nếu cần)."""
    import pyodbc
    conn = pyodbc.connect(MASTER_CONNECTION_STRING)
    return conn


def ensure_database_exists():
    """Kiểm tra và tạo database nếu chưa tồn tại."""
    import pyodbc
    
    conn = get_master_connection()
    cursor = conn.cursor()
    
    # Check if DB exists
    cursor.execute("""
        SELECT name FROM sys.databases WHERE name = ?
    """, (SQL_DATABASE,))
    
    exists = cursor.fetchone()
    
    if not exists:
        print(f"   📦 Tạo database {SQL_DATABASE}...")
        conn.close()
        # Mở connection mới với autocommit để CREATE DATABASE
        conn = pyodbc.connect(MASTER_CONNECTION_STRING)
        conn.autocommit = True  # Bắt buộc cho CREATE DATABASE
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE [{SQL_DATABASE}];")
        print(f"   ✅ Database {SQL_DATABASE} đã được tạo!")
    else:
        print(f"   ✅ Database {SQL_DATABASE} đã tồn tại.")
    
    conn.close()


def load_vcb_data_csv_format():
    """
    Load dữ liệu VCB từ SQL Server theo đúng format của VCB_data.csv.
    
    Trả về DataFrame với 11 cột:
        Date, Close, High, Low, Open, Volume, RSI, MA10, MA20, MA50, MACD
    
    Giống hệt như: pd.read_csv("data/VCB_data.csv")
    """
    conn = get_connection()
    
    query = """
    WITH RankedPrices AS (
        SELECT 
            dsp.PriceID,
            dsp.TradingDate,
            dsp.ClosePrice,
            dsp.HighPrice,
            dsp.LowPrice,
            dsp.OpenPrice,
            dsp.Volume,
            ROW_NUMBER() OVER (PARTITION BY dsp.TradingDate ORDER BY dsp.PriceID ASC) as rn
        FROM [dbo].[DAILY_STOCK_PRICES] dsp
        WHERE dsp.Ticker = 'VCB'
    )
    SELECT 
        CAST(rp.TradingDate AS VARCHAR(10)) AS [Date],
        rp.ClosePrice AS [Close],
        rp.HighPrice AS [High],
        rp.LowPrice AS [Low],
        rp.OpenPrice AS [Open],
        rp.Volume AS [Volume],
        ti.RSI AS [RSI],
        ti.MA10 AS [MA10],
        ti.MA20 AS [MA20],
        ti.MA50 AS [MA50],
        ti.MACD AS [MACD]
    FROM RankedPrices rp
    INNER JOIN [dbo].[TECHNICAL_INDICATORS] ti ON rp.PriceID = ti.PriceID
    WHERE rp.rn = 1
    ORDER BY rp.TradingDate ASC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    return df


def load_vcb_raw_prices():
    """Load dữ liệu giá thô VCB từ SQL Server."""
    conn = get_connection()
    
    query = """
    SELECT 
        TradingDate,
        OpenPrice,
        HighPrice,
        LowPrice,
        ClosePrice,
        Volume
    FROM [dbo].[DAILY_STOCK_PRICES]
    WHERE Ticker = 'VCB'
    ORDER BY TradingDate ASC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    return df


def load_all_tickers_prices():
    """Load dữ liệu giá của tất cả tickers từ SQL Server."""
    conn = get_connection()
    
    query = """
    SELECT 
        Ticker,
        TradingDate,
        OpenPrice,
        HighPrice,
        LowPrice,
        ClosePrice,
        Volume
    FROM [dbo].[DAILY_STOCK_PRICES]
    ORDER BY Ticker, TradingDate ASC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    return df


def load_technical_indicators(ticker='VCB'):
    """Load technical indicators từ SQL Server."""
    conn = get_connection()
    
    query = """
    SELECT 
        dsp.TradingDate,
        ti.MA10,
        ti.MA20,
        ti.MA50,
        ti.RSI,
        ti.MACD,
        ti.BollingerUpper,
        ti.BollingerLower,
        ti.TradingSignal
    FROM [dbo].[DAILY_STOCK_PRICES] dsp
    INNER JOIN [dbo].[TECHNICAL_INDICATORS] ti ON dsp.PriceID = ti.PriceID
    WHERE dsp.Ticker = ?
    ORDER BY dsp.TradingDate ASC
    """
    
    df = pd.read_sql(query, conn, params=[ticker])
    conn.close()
    
    return df


def load_trade_history():
    """
    Load dữ liệu giao dịch từ SQL Server (thay thế trade_history.csv).
    """
    conn = get_connection()
    
    try:
        query = """
        SELECT 
            TradeID,
            TradeDate,
            Action,
            Ticker,
            Price,
            Quantity,
            TotalValue,
            Status,
            Notes
        FROM [dbo].[TRADE_LOG]
        ORDER BY TradeDate DESC, TradeID DESC
        """
        
        df = pd.read_sql(query, conn)
    except Exception:
        df = pd.DataFrame(columns=['TradeID', 'TradeDate', 'Action', 'Ticker', 
                                    'Price', 'Quantity', 'TotalValue', 'Status', 'Notes'])
    
    conn.close()
    
    return df


def save_trade_to_sql(action, ticker, price, quantity, notes=""):
    """Lưu lệnh giao dịch mới vào SQL Server."""
    conn = get_connection()
    cursor = conn.cursor()
    
    trade_date = pd.Timestamp.now().strftime('%Y-%m-%d')
    total_value = round(price * quantity, 2)
    
    cursor.execute("""
        INSERT INTO [dbo].[TRADE_LOG] 
        (TradeDate, Action, Ticker, Price, Quantity, TotalValue, Status, Notes)
        VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
    """, trade_date, action.upper(), ticker.upper(), price, quantity, total_value, notes)
    
    conn.commit()
    conn.close()


def verify_data_integrity():
    """Kiểm tra tính toàn vẹn dữ liệu trong SQL Server."""
    conn = get_connection()
    cursor = conn.cursor()
    
    results = {}
    
    cursor.execute("SELECT COUNT(*) FROM [dbo].[COMPANIES]")
    results['companies_count'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*), MIN(TradingDate), MAX(TradingDate) FROM [dbo].[DAILY_STOCK_PRICES]")
    row = cursor.fetchone()
    results['prices_count'] = row[0]
    results['prices_first_date'] = str(row[1]) if row[1] else None
    results['prices_last_date'] = str(row[2]) if row[2] else None
    
    cursor.execute("SELECT Ticker, COUNT(*) FROM [dbo].[DAILY_STOCK_PRICES] GROUP BY Ticker ORDER BY Ticker")
    results['prices_by_ticker'] = {str(r[0]): r[1] for r in cursor.fetchall()}
    
    cursor.execute("SELECT COUNT(*) FROM [dbo].[TECHNICAL_INDICATORS]")
    results['indicators_count'] = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM [dbo].[TECHNICAL_INDICATORS] ti
        JOIN [dbo].[DAILY_STOCK_PRICES] dsp ON ti.PriceID = dsp.PriceID
        WHERE dsp.Ticker = 'VCB'
    """)
    results['vcb_indicators_count'] = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT TradingSignal, COUNT(*) FROM [dbo].[TECHNICAL_INDICATORS]
        GROUP BY TradingSignal ORDER BY COUNT(*) DESC
    """)
    results['signals_distribution'] = {str(r[0]): r[1] for r in cursor.fetchall()}
    
    cursor.execute("""
        SELECT COUNT(*) FROM [dbo].[TECHNICAL_INDICATORS] ti
        LEFT JOIN [dbo].[DAILY_STOCK_PRICES] dsp ON ti.PriceID = dsp.PriceID
        WHERE dsp.PriceID IS NULL
    """)
    results['orphaned_indicators'] = cursor.fetchone()[0]
    
    conn.close()
    
    return results


def check_sql_server_available():
    """Kiểm tra xem SQL Server có sẵn không."""
    try:
        conn = get_master_connection()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Không thể kết nối SQL Server: {e}")
        return False


# Streamlit cache
try:
    import streamlit as st
    
    @st.cache_resource
    def get_cached_connection():
        return get_connection()
    
    @st.cache_data(ttl=300)
    def load_vcb_cached():
        return load_vcb_data_csv_format()
    
except ImportError:
    pass
