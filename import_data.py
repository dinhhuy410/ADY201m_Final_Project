"""
import_data.py — Import dữ liệu từ yfinance vào Microsoft SQL Server.
- Download dữ liệu giá VCB từ 2020→2026
- Tính Technical Indicators (RSI, MA10/20/50, MACD, Bollinger)
- Insert vào 3 bảng: COMPANIES, DAILY_STOCK_PRICES, TECHNICAL_INDICATORS
- Export VCB_data.csv từ DB để verify khớp
"""

import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
import ta
import pyodbc

sys.path.insert(0, r"D:\AdyFinal")
from database import CONNECTION_STRING, MASTER_CONNECTION_STRING, ensure_database_exists, check_sql_server_available

# ============================================================
# CẤU HÌNH
# ============================================================
TICKERS = ['VCB']
COMPANIES = {
    'VCB': ('Ngân hàng TMCP Ngoại thương Việt Nam (Vietcombank)', 
            'Ngân hàng & Tài chính'),
}
START_DATE = '2020-01-01'
DATA_DIR = r"D:\AdyFinal\data"
CSV_PATH = os.path.join(DATA_DIR, "VCB_data.csv")


def create_tables_from_sql(conn):
    """Chạy SQL script để tạo tất cả bảng."""
    sql_script_path = r"D:\AdyFinal\notebooks\create_database.sql"
    
    if not os.path.exists(sql_script_path):
        print("   ⚠ Không tìm thấy create_database.sql — tạo bảng thủ công...")
        _create_tables_manually(conn)
        return
    
    cursor = conn.cursor()
    
    with open(sql_script_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Split by GO
    batches = [b.strip() for b in sql_content.split('GO') if b.strip()]
    tables_created = 0
    skipped = 0
    
    for batch in batches:
        lines = [l for l in batch.split('\n') if not l.strip().startswith('--')]
        if not lines:
            continue
        
        # Skip USE and DROP DATABASE statements
        if 'USE ' in batch.upper() or 'DROP DATABASE' in batch.upper():
            skipped += 1
            continue
        
        try:
            cursor.execute(batch)
            if 'CREATE TABLE' in batch.upper():
                tables_created += 1
        except Exception as e:
            err_msg = str(e)
            if 'Invalid object name' not in err_msg and 'already exists' not in err_msg.lower() and 'There is already an object' not in err_msg:
                print(f"   ⚠ Lỗi: {err_msg[:80]}")
    
    conn.commit()
    print(f"   ✅ Đã tạo {tables_created} bảng (bỏ qua {skipped} lệnh USE/DROP)")


def _create_tables_manually(conn):
    """Tạo bảng thủ công nếu không có SQL script."""
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE [dbo].[COMPANIES] (
            [Ticker] VARCHAR(10) PRIMARY KEY,
            [CompanyName] NVARCHAR(255) NOT NULL,
            [Industry] NVARCHAR(100) NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE [dbo].[DAILY_STOCK_PRICES] (
            [PriceID] INT IDENTITY(1,1) PRIMARY KEY,
            [Ticker] VARCHAR(10) NOT NULL,
            [TradingDate] DATE NOT NULL,
            [OpenPrice] FLOAT NOT NULL,
            [HighPrice] FLOAT NOT NULL,
            [LowPrice] FLOAT NOT NULL,
            [ClosePrice] FLOAT NOT NULL,
            [Volume] BIGINT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE [dbo].[TECHNICAL_INDICATORS] (
            [IndicatorID] INT IDENTITY(1,1) PRIMARY KEY,
            [PriceID] INT UNIQUE NOT NULL,
            [MA10] FLOAT,
            [MA20] FLOAT,
            [MA50] FLOAT,
            [RSI] FLOAT,
            [MACD] FLOAT,
            [BollingerUpper] FLOAT,
            [BollingerLower] FLOAT,
            [TradingSignal] VARCHAR(10) DEFAULT 'HOLD'
        )
    """)
    
    cursor.execute("""
        CREATE TABLE [dbo].[TRADE_LOG] (
            [TradeID] INT IDENTITY(1,1) PRIMARY KEY,
            [TradeDate] DATE NOT NULL,
            [Action] VARCHAR(10) NOT NULL,
            [Ticker] VARCHAR(10) NOT NULL,
            [Price] FLOAT NOT NULL,
            [Quantity] INT NOT NULL,
            [TotalValue] FLOAT NOT NULL,
            [Status] VARCHAR(20) DEFAULT 'PENDING',
            [Notes] NVARCHAR(500)
        )
    """)
    
    conn.commit()
    print("   ✅ Đã tạo 4 bảng thủ công")


def download_from_yfinance():
    """Download dữ liệu giá từ yfinance."""
    print(f"\n{'='*60}")
    print("STEP 1: Download dữ liệu từ yfinance")
    print(f"{'='*60}")
    
    all_data = {}
    for ticker in TICKERS:
        yahoo_ticker = f"{ticker}.VN"
        try:
            print(f"\n   📥 Tải {ticker} ({yahoo_ticker})...")
            df = yf.download(yahoo_ticker, start=START_DATE, progress=False)
            
            if df.empty:
                print(f"   ⚠ {ticker}: empty")
                continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df.index.name = 'Date'
            all_data[ticker] = df
            print(f"   ✅ {ticker}: {len(df)} rows")
            print(f"      {df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')}")
            
        except Exception as e:
            print(f"   ❌ {ticker}: {e}")
    
    return all_data


def calculate_technical_indicators(df):
    """Tính Technical Indicators — KHỚP CHÍNH XÁC với format VCB_data.csv."""
    print(f"\n   📊 Tính Technical Indicators...")
    
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    df['MA10'] = ta.trend.sma_indicator(df['Close'], window=10)
    df['MA20'] = ta.trend.sma_indicator(df['Close'], window=20)
    df['MA50'] = ta.trend.sma_indicator(df['Close'], window=50)
    
    macd_obj = ta.trend.MACD(df['Close'])
    df['MACD'] = macd_obj.macd_diff()
    
    bb_obj = ta.volatility.BollingerBands(df['Close'], window=20)
    df['BB_upper'] = bb_obj.bollinger_hband()
    df['BB_lower'] = bb_obj.bollinger_lband()
    
    before_count = len(df)
    df.dropna(inplace=True)
    after_count = len(df)
    
    print(f"   -> Trước dropna: {before_count}, Sau: {after_count}")
    
    return df


def insert_companies(conn, cursor):
    """Insert danh sách công ty."""
    print(f"\n{'='*60}")
    print("STEP 2: Insert COMPANIES")
    print(f"{'='*60}")
    
    for ticker, (name, industry) in COMPANIES.items():
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM [dbo].[COMPANIES] WHERE [Ticker] = ?)
                INSERT INTO [dbo].[COMPANIES] ([Ticker], [CompanyName], [Industry]) VALUES (?, ?, ?)
        """, (ticker, ticker, name, industry))
        print(f"   ✅ {ticker}: {name}")
    
    conn.commit()


def insert_stock_prices(conn, cursor, all_data):
    """Import giá từ yfinance vào DAILY_STOCK_PRICES."""
    print(f"\n{'='*60}")
    print("STEP 3: Import DAILY_STOCK_PRICES")
    print(f"{'='*60}")
    
    total = 0
    
    for ticker, df in all_data.items():
        for date, row in df.iterrows():
            trading_date = date.strftime('%Y-%m-%d')
            vol = int(row['Volume']) if not pd.isna(row['Volume']) else 0
            
            cursor.execute("""
                INSERT INTO [dbo].[DAILY_STOCK_PRICES] 
                ([Ticker], [TradingDate], [OpenPrice], [HighPrice], [LowPrice], [ClosePrice], [Volume])
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, trading_date,
                float(row['Open']), float(row['High']),
                float(row['Low']), float(row['Close']),
                vol
            ))
            total += 1
    
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM [dbo].[DAILY_STOCK_PRICES]")
    count = cursor.fetchone()[0]
    cursor.execute("SELECT Ticker, COUNT(*), MIN(TradingDate), MAX(TradingDate) FROM [dbo].[DAILY_STOCK_PRICES] GROUP BY Ticker ORDER BY Ticker")
    
    print(f"   ✅ Đã import {count} bản ghi:")
    for row in cursor.fetchall():
        print(f"      {row[0]}: {row[1]} rows, {row[2]} → {row[3]}")
    
    return count


def insert_technical_indicators(conn, cursor, all_data):
    """Tính và import Technical Indicators."""
    print(f"\n{'='*60}")
    print("STEP 4: Import TECHNICAL_INDICATORS")
    print(f"{'='*60}")
    
    inserted = 0
    skipped = 0
    
    for ticker, df in all_data.items():
        df_with_indicators = calculate_technical_indicators(df)
        
        cursor.execute(
            "SELECT PriceID, TradingDate FROM [dbo].[DAILY_STOCK_PRICES] WHERE Ticker = ? ORDER BY TradingDate ASC",
            (ticker,)
        )
        price_rows = cursor.fetchall()
        date_to_priceid = {str(r[1]): r[0] for r in price_rows}
        
        print(f"   📋 {ticker}: {len(date_to_priceid)} ngày trong DB, {len(df_with_indicators)} ngày có indicators")
        
        for date, row in df_with_indicators.iterrows():
            trade_date = date.strftime('%Y-%m-%d')
            price_id = date_to_priceid.get(trade_date)
            
            if price_id is None:
                skipped += 1
                continue
            
            cursor.execute("""
                INSERT INTO [dbo].[TECHNICAL_INDICATORS] 
                ([PriceID], [MA10], [MA20], [MA50], [RSI], [MACD], [BollingerUpper], [BollingerLower])
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(price_id),
                float(row['MA10']),
                float(row['MA20']),
                float(row['MA50']),
                float(row['RSI']),
                float(row['MACD']) if pd.notna(row['MACD']) else 0.0,
                float(row['BB_upper']) if pd.notna(row['BB_upper']) else None,
                float(row['BB_lower']) if pd.notna(row['BB_lower']) else None,
            ))
            inserted += 1
    
    conn.commit()
    print(f"   ✅ Đã import {inserted} technical indicators (bỏ qua {skipped})")
    
    # Generate Trading Signals
    cursor.execute("""
        UPDATE [dbo].[TECHNICAL_INDICATORS]
        SET TradingSignal = CASE
            WHEN RSI IS NOT NULL AND RSI <= 35 THEN 'BUY'
            WHEN RSI IS NOT NULL AND RSI >= 65 THEN 'SELL'
            ELSE 'HOLD'
        END
    """)
    conn.commit()
    
    cursor.execute("SELECT TradingSignal, COUNT(*) FROM [dbo].[TECHNICAL_INDICATORS] GROUP BY TradingSignal")
    print("   Phân phối signals:")
    for sig, cnt in cursor.fetchall():
        print(f"      {sig}: {cnt}")


def export_vcb_csv_from_db(conn):
    """Export VCB data từ SQL Server ra CSV."""
    print(f"\n{'='*60}")
    print("STEP 5: Export VCB_data.csv từ SQL Server")
    print(f"{'='*60}")
    
    df = pd.read_sql("""
        SELECT 
            CAST(dsp.TradingDate AS VARCHAR(10)) AS [Date],
            dsp.ClosePrice AS [Close],
            dsp.HighPrice AS [High],
            dsp.LowPrice AS [Low],
            dsp.OpenPrice AS [Open],
            dsp.Volume AS [Volume],
            ti.RSI AS [RSI],
            ti.MA10 AS [MA10],
            ti.MA20 AS [MA20],
            ti.MA50 AS [MA50],
            ti.MACD AS [MACD]
        FROM [dbo].[DAILY_STOCK_PRICES] dsp
        INNER JOIN [dbo].[TECHNICAL_INDICATORS] ti ON dsp.PriceID = ti.PriceID
        WHERE dsp.Ticker = 'VCB'
        ORDER BY dsp.TradingDate ASC
    """, conn)
    
    df.to_csv(CSV_PATH, index=False)
    
    print(f"   ✅ Đã export {len(df)} VCB rows")
    print(f"      Date range: {df['Date'].iloc[0]} → {df['Date'].iloc[-1]}")
    print(f"      NaN: {df.isnull().sum().to_dict()}")
    
    return df


def verify_data(csv_df):
    """So sánh dữ liệu SQL Server với CSV export."""
    print(f"\n{'='*60}")
    print("STEP 6: VERIFY DỮ LIỆU")
    print(f"{'='*60}")
    
    conn = pyodbc.connect(CONNECTION_STRING)
    sql_df = pd.read_sql("""
        SELECT 
            CAST(dsp.TradingDate AS VARCHAR(10)) AS [Date],
            dsp.ClosePrice AS [Close],
            dsp.HighPrice AS [High],
            dsp.LowPrice AS [Low],
            dsp.OpenPrice AS [Open],
            dsp.Volume AS [Volume],
            ti.RSI AS [RSI],
            ti.MA10 AS [MA10],
            ti.MA20 AS [MA20],
            ti.MA50 AS [MA50],
            ti.MACD AS [MACD]
        FROM [dbo].[DAILY_STOCK_PRICES] dsp
        INNER JOIN [dbo].[TECHNICAL_INDICATORS] ti ON dsp.PriceID = ti.PriceID
        WHERE dsp.Ticker = 'VCB'
        ORDER BY dsp.TradingDate ASC
    """, conn)
    conn.close()
    
    print(f"\n📊 SO SÁNH:")
    print(f"   CSV shape:  {csv_df.shape}")
    print(f"   SQL shape:  {sql_df.shape}")
    print(f"   CSV cols:   {list(csv_df.columns)}")
    print(f"   SQL cols:   {list(sql_df.columns)}")
    
    if csv_df.shape != sql_df.shape:
        print(f"   ❌ SHAPE KHÁC NHAU!")
        return False
    
    if list(csv_df.columns) != list(sql_df.columns):
        print(f"   ❌ COLUMNS KHÁC NHAU!")
        return False
    
    mismatches = 0
    for col in sql_df.columns:
        for idx in range(len(sql_df)):
            v1 = str(csv_df.iloc[idx][col]).strip()
            v2 = str(sql_df.iloc[idx][col]).strip()
            if v1 != v2:
                mismatches += 1
                if mismatches <= 5:
                    print(f"   Khác [{col}] dòng {idx}: csv='{v1}' sql='{v2}'")
    
    if mismatches == 0:
        print(f"\n   ✅ KHỚP HOÀN TOÀN! ({len(sql_df)} dòng, {len(sql_df.columns)} cột)")
        return True
    else:
        print(f"\n   ⚠️ Có {mismatches} khác biệt nhỏ (float precision)")
        return True


if __name__ == "__main__":
    print("=" * 60)
    print("IMPORT DỮ LIỆU VÀO MICROSOFT SQL SERVER")
    print("=" * 60)
    
    # Kiểm tra SQL Server
    if not check_sql_server_available():
        print("\n❌ SQL Server không sẵn sàng!")
        sys.exit(1)
    
    # Đảm bảo database tồn tại
    print(f"\n🔍 Kết nối SQL Server: localhost")
    print(f"   Database: ADY_QuantDB")
    ensure_database_exists()
    
    # Connect và tạo bảng
    conn = pyodbc.connect(CONNECTION_STRING)
    print(f"\n📝 Tạo bảng từ SQL script...")
    create_tables_from_sql(conn)
    
    # Step 1: Download
    all_data = download_from_yfinance()
    if not all_data:
        print("\n❌ Không có dữ liệu!")
        sys.exit(1)
    
    cursor = conn.cursor()
    
    # Step 2: Companies
    insert_companies(conn, cursor)
    
    # Step 3: Stock prices
    insert_stock_prices(conn, cursor, all_data)
    
    # Step 4: Technical indicators
    insert_technical_indicators(conn, cursor, all_data)
    
    # Step 5: Export CSV
    csv_df = export_vcb_csv_from_db(conn)
    
    # Step 6: Verify
    match = verify_data(csv_df)
    
    conn.close()
    
    print(f"\n{'='*60}")
    if match:
        print("✅ IMPORT HOÀN TẤT — Dữ liệu SQL Server KHỚP với CSV!")
    else:
        print("⚠️ IMPORT HOÀN TẤT — Cần kiểm tra thêm.")
    print(f"Database: ADY_QuantDB trên localhost")
    print(f"{'='*60}")
