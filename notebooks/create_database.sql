-- ============================================================
-- SQL Script: Tạo Database ADY_QuantDB trên Microsoft SQL Server
-- Schema: 3 bảng chuẩn + TRADE_LOG với đầy đủ FOREIGN KEY
-- Dữ liệu: VCB (Vietcombank) 2020-01-01 → hiện tại
-- Chỉ báo: RSI(14), MA10, MA20, MA50, MACD, Bollinger Bands
-- Trading Signal: BUY (<35), SELL (>65), HOLD
-- ============================================================

USE master;
GO

-- ==========================================
-- 1. TẠO DATABASE
-- ==========================================
IF DB_ID('ADY_QuantDB') IS NOT NULL
    DROP DATABASE ADY_QuantDB;
GO

CREATE DATABASE [ADY_QuantDB];
GO

USE [ADY_QuantDB];
GO

-- ==========================================
-- 2. TẠO BẢNG COMPANIES
-- ==========================================
CREATE TABLE [dbo].[COMPANIES] (
    [Ticker] VARCHAR(10) PRIMARY KEY,
    [CompanyName] NVARCHAR(255) NOT NULL,
    [Industry] NVARCHAR(100) NOT NULL
);
GO

-- ==========================================
-- 3. TẠO BẢNG DAILY_STOCK_PRICES
--    - PriceID: PRIMARY KEY tự tăng
--    - Ticker: FOREIGN KEY → COMPANIES(Ticker)
-- ==========================================
CREATE TABLE [dbo].[DAILY_STOCK_PRICES] (
    [PriceID] INT IDENTITY(1,1) PRIMARY KEY,
    [Ticker] VARCHAR(10) NOT NULL,
    [TradingDate] DATE NOT NULL,
    [OpenPrice] FLOAT NOT NULL,
    [HighPrice] FLOAT NOT NULL,
    [LowPrice] FLOAT NOT NULL,
    [ClosePrice] FLOAT NOT NULL,
    [Volume] BIGINT NOT NULL,
    CONSTRAINT [FK_DailyStock_Companies] 
        FOREIGN KEY ([Ticker]) REFERENCES [dbo].[COMPANIES]([Ticker]) ON DELETE CASCADE
);
GO

-- Index để query nhanh theo ticker và ngày
CREATE INDEX [IX_DailyStock_Ticker_Date] 
    ON [dbo].[DAILY_STOCK_PRICES]([Ticker], [TradingDate]);
GO

-- ==========================================
-- 4. TẠO BẢNG TECHNICAL_INDICATORS
--    - IndicatorID: PRIMARY KEY tự tăng
--    - PriceID: UNIQUE + FOREIGN KEY → DAILY_STOCK_PRICES(PriceID)
-- ==========================================
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
    [TradingSignal] VARCHAR(10) DEFAULT 'HOLD',
    CONSTRAINT [FK_TechIndicators_DailyStock] 
        FOREIGN KEY ([PriceID]) REFERENCES [dbo].[DAILY_STOCK_PRICES]([PriceID]) ON DELETE CASCADE
);
GO

-- Index để join nhanh
CREATE INDEX [IX_TechIndicators_PriceID] 
    ON [dbo].[TECHNICAL_INDICATORS]([PriceID]);
GO

-- ==========================================
-- 5. TẠO BẢNG TRADE_LOG (nhật ký giao dịch)
--    - TradeID: PRIMARY KEY tự tăng
--    - Ticker: FOREIGN KEY → COMPANIES(Ticker)
-- ==========================================
CREATE TABLE [dbo].[TRADE_LOG] (
    [TradeID] INT IDENTITY(1,1) PRIMARY KEY,
    [TradeDate] DATE NOT NULL,
    [Action] VARCHAR(10) NOT NULL,
    [Ticker] VARCHAR(10) NOT NULL,
    [Price] FLOAT NOT NULL,
    [Quantity] INT NOT NULL,
    [TotalValue] FLOAT NOT NULL,
    [Status] VARCHAR(20) DEFAULT 'PENDING',
    [Notes] NVARCHAR(500),
    CONSTRAINT [FK_TradeLog_Companies] 
        FOREIGN KEY ([Ticker]) REFERENCES [dbo].[COMPANIES]([Ticker]) ON DELETE CASCADE
);
GO

-- ==========================================
-- 6. VIEW: Dữ liệu tổng hợp giống CSV
-- ==========================================
CREATE VIEW [dbo].[vw_VCB_Data_CSV] AS
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
ORDER BY dsp.TradingDate ASC;
GO

-- ==========================================
-- 7. KIỂM TRA RELATIONSHIPS
-- ==========================================
PRINT '=== KIỂM TRA FOREIGN KEYS ===';
SELECT 
    fk.name AS ForeignKeyName,
    OBJECT_NAME(fk.parent_object_id) AS TableName,
    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS ColumnName,
    OBJECT_NAME(fk.referenced_object_id) AS ReferencedTable,
    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS ReferencedColumn
FROM sys.foreign_keys AS fk
INNER JOIN sys.foreign_key_columns AS fkc 
    ON fk.OBJECT_ID = fkc.constraint_object_id
ORDER BY TableName, ColumnName;

PRINT '';
PRINT '✅ DATABASE CREATED SUCCESSFULLY — All FOREIGN KEYS defined!';
