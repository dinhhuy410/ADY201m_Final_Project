"""
load_data.py — Helper module để load dữ liệu từ SQL Server.
Thay thế hoàn toàn pd.read_csv('data/VCB_data.csv') trong notebooks.

Sử dụng:
    from load_data import load_vcb_data
    
    df = load_vcb_data()  # Trả về DataFrame giống hệt VCB_data.csv
"""

import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import load_vcb_data_csv_format


def load_vcb_data():
    """
    Load dữ liệu VCB từ SQL Server.
    
    Trả về DataFrame với 11 cột:
        Date, Close, High, Low, Open, Volume, RSI, MA10, MA20, MA50, MACD
    
    Giống hệt như: pd.read_csv("data/VCB_data.csv", index_col=0, parse_dates=True)
    """
    df = load_vcb_data_csv_format()
    
    # Chuyển Date sang datetime và set làm index (giống notebook gốc)
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)
    
    return df


def load_vcb_data_raw():
    """
    Load dữ liệu giá thô VCB từ SQL Server (không có indicators).
    
    Trả về DataFrame với các cột:
        TradingDate, OpenPrice, HighPrice, LowPrice, ClosePrice, Volume
    """
    from database import load_vcb_raw_prices
    df = load_vcb_raw_prices()
    df['TradingDate'] = pd.to_datetime(df['TradingDate'])
    df.set_index('TradingDate', inplace=True)
    return df
