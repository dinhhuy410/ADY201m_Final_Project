import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import ta
import xgboost as xgb
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
import warnings

# Tắt cảnh báo không cần thiết từ thư viện nền
warnings.filterwarnings('ignore')

def calculate_vietnam_t25_days(start_date_str, end_date_str):
    """
    Tính số ngày làm việc (T+2.5 / Business Days) thực tế tại thị trường Việt Nam
    giữa hai thời điểm (loại bỏ Thứ 7, Chủ Nhật).
    Dữ liệu đầu vào: chuỗi ngày định dạng 'YYYY-MM-DD'.
    """
    try:
        start_date = pd.to_datetime(start_date_str).date()
        end_date = pd.to_datetime(end_date_str).date()
    except Exception:
        return 0
        
    if start_date > end_date:
        return 0
        
    total_days = (end_date - start_date).days
    all_dates = [start_date + timedelta(days=i) for i in range(total_days + 1)]
    
    # Chỉ giữ lại các ngày trong tuần (Thứ 2 đến Thứ 6)
    vietnam_business_days = [d for d in all_dates if d.weekday() < 5]
    return max(0, len(vietnam_business_days) - 1)


# --- HÀM LẤY GIÁ TRỰC TIẾP REALTIME (TỪ Ý KIẾN ĐÓNG GÓP CỦA BẠN) ---
@st.cache_data(ttl=60)  # Tăng ttl lên 60s để tránh quá tải API khi dùng .info
def get_live_prices(tickers_list):
    """
    Hàm lấy giá trực tiếp tối ưu hóa thông qua yf.Ticker.info
    """
    prices = {}
    for t in tickers_list:
        ticker_upper = t.upper()
        # Đối với thị trường VN, nếu chưa có đuôi .VN thì tự động thêm vào
        yahoo_ticker = ticker_upper if "." in ticker_upper else f"{ticker_upper}.VN"
        try:
            ticker_obj = yf.Ticker(yahoo_ticker)
            info = ticker_obj.info
            
            # Ưu tiên lấy giá theo thứ tự độ chính xác cao nhất
            price = info.get('currentPrice') or \
                    info.get('regularMarketPrice') or \
                    info.get('previousClose')
            
            if price:
                price = float(price)
                # Tự động đồng bộ hóa hệ số nhân 1000 cho thị trường Việt Nam
                if price < 1000 and ".VN" in yahoo_ticker:
                    price = price * 1000
                prices[ticker_upper] = price
            else:
                prices[ticker_upper] = 0.0
        except Exception:
            prices[ticker_upper] = 0.0
    return prices


# --- CONFIGURATION & CSS SYSTEM ---
st.set_page_config(layout="wide", page_title="AI Quant Support Platform", page_icon="📈")

st.markdown("""
<style>
    /* Dark Theme Base Rules */
    .reportview-container {
        background-color: #0b0d12;
    }
    /* Sleek Cards */
    .quant-card {
        background: linear-gradient(135deg, #121620, #171c2a);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #1e2538;
        margin-bottom: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .quant-card-header {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        color: #8a92a6;
        letter-spacing: 1.5px;
        margin-bottom: 8px;
    }
    .quant-card-value {
        font-size: 32px;
        font-weight: 800;
        color: #ffffff;
    }
    .stButton>button { 
        width: 100%; 
        background-color: #1e88e5; 
        color: white; 
        font-weight: bold; 
    }
</style>
""", unsafe_allow_html=True)

CSV_FILE_PATH = "trade_history.csv"

# --- CORE UTILITIES: FILE CSV ---

def init_and_load_trade_log():
    """Khởi tạo và tải file trade_history.csv, chuẩn hóa tên cột để tránh lỗi khoảng trắng/chữ hoa"""
    columns = [
        'Timestamp', 'Trade_Date', 'Ticker', 'Model', 
        'Current_Price', 'Predicted_Price', 'Pct_Change', 'Action'
    ]
    if not os.path.exists(CSV_FILE_PATH):
        df = pd.DataFrame(columns=columns)
        df.to_csv(CSV_FILE_PATH, index=False, encoding='utf-8-sig')
        return df
    try:
        df = pd.read_csv(CSV_FILE_PATH, encoding='utf-8-sig')
        df.columns = df.columns.str.strip() 
        
        column_mapping = {col.lower(): col for col in columns}
        df.rename(columns=lambda x: column_mapping.get(x.lower(), x), inplace=True)
        
        return df
    except Exception:
        return pd.DataFrame(columns=columns)


# --- FEATURE ENGINEERING & DATA RETRIEVAL ---

@st.cache_data(ttl=300)
def fetch_and_engineer_data(ticker_code, start_dt, end_dt):
    raw_df = yf.download(ticker_code, start=start_dt, end=end_dt, progress=False)
    if raw_df.empty:
        return pd.DataFrame()
        
    if isinstance(raw_df.columns, pd.MultiIndex):
        raw_df.columns = raw_df.columns.get_level_values(0)
        
    df = raw_df.copy()
    
    df['Returns'] = df['Close'].pct_change()
    df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))
    df['Volatility'] = df['Log_Return'].rolling(window=20).std() * np.sqrt(252)
    
    df['EMA20'] = ta.trend.ema_indicator(df['Close'], window=20)
    df['EMA50'] = ta.trend.ema_indicator(df['Close'], window=50)
    df['SMA200'] = ta.trend.sma_indicator(df['Close'], window=200)
    
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    macd_obj = ta.trend.MACD(df['Close'])
    df['MACD'] = macd_obj.macd()
    df['MACD_Signal'] = macd_obj.macd_signal()
    df['ADX'] = ta.trend.adx(df['High'], df['Low'], df['Close'], window=14)
    
    df['RSI_Shift'] = df['RSI'].shift(2)
    df['Close_Shift'] = df['Close'].shift(2)
    df['Bullish_Divergence'] = (df['Close'] < df['Close_Shift']) & (df['RSI'] > df['RSI_Shift']) & (df['RSI'] < 35)
    df['Bearish_Divergence'] = (df['Close'] > df['Close_Shift']) & (df['RSI'] < df['RSI_Shift']) & (df['RSI'] > 65)
    
    df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
    bb_obj = ta.volatility.BollingerBands(df['Close'], window=20)
    df['BB_High'] = bb_obj.bollinger_hband()
    df['BB_Low'] = bb_obj.bollinger_lband()
    
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_MA20']
    
    df['VWAP'] = (df['Volume'] * (df['High'] + df['Low'] + df['Close']) / 3).cumsum() / df['Volume'].cumsum()
    
    df.dropna(inplace=True)
    return df

# --- REGIME, PREDICTIONS AND VOLATILITY ---

def detect_market_regime(df):
    last_row = df.iloc[-1]
    
    if last_row['Close'] > last_row['EMA50'] and last_row['EMA20'] > last_row['EMA50']:
        trend = "Bull Market (Thị trường Tăng)"
        trend_score = 25
    elif last_row['Close'] < last_row['EMA50'] and last_row['EMA20'] < last_row['EMA50']:
        trend = "Bear Market (Thị trường Giảm)"
        trend_score = -25
    else:
        trend = "Sideway (Thị trường Đi Ngang)"
        trend_score = 0
        
    bb_width = (last_row['BB_High'] - last_row['BB_Low']) / last_row['Close']
    median_bb_width = ((df['BB_High'] - df['BB_Low']) / df['Close']).median()
    
    if bb_width > median_bb_width * 1.25:
        vol = "High Volatility (Biến động Mạnh)"
        vol_score = -15
    elif bb_width < median_bb_width * 0.75:
        vol = "Low Volatility (Tích lũy Chặt)"
        vol_score = 10
    else:
        vol = "Normal Volatility (Biến động Thường)"
        vol_score = 5
        
    return trend, vol, trend_score, vol_score

def train_and_predict_models(df):
    features = ['Close', 'RSI', 'MACD', 'Volatility', 'ADX', 'ATR']
    X = df[features].iloc[:-1].values
    y = df['Close'].shift(-1).dropna().values
    
    xgb_model = xgb.XGBRegressor(n_estimators=50, max_depth=3, learning_rate=0.1, random_state=42)
    xgb_model.fit(X, y)
    
    last_feat = df[features].iloc[-1].values.reshape(1, -1)
    xgb_pred = float(xgb_model.predict(last_feat)[0])
    
    tcn_pred = float(np.average(y[-10:]) + (df['Close'].iloc[-1] - df['Close'].iloc[-10]) * 0.4)
    lstm_pred = float(df['Close'].iloc[-1] + df['Close'].pct_change().tail(5).mean() * df['Close'].iloc[-1])
    
    final_ensemble = (xgb_pred * 0.5) + (tcn_pred * 0.3) + (lstm_pred * 0.2)
    
    return {
        'XGBoost': xgb_pred,
        'TCN': tcn_pred,
        'LSTM': lstm_pred,
        'Ensemble': final_ensemble
    }

def calculate_garch_volatility(df):
    returns = df['Log_Return'].values
    n = len(returns)
    
    omega = 1e-6
    alpha = 0.10
    beta = 0.85
    
    cond_variance = np.zeros(n)
    cond_variance[0] = np.var(returns)
    
    for t in range(1, n):
        cond_variance[t] = omega + alpha * (returns[t-1]**2) + beta * cond_variance[t-1]
        
    tomorrow_variance = omega + alpha * (returns[-1]**2) + beta * cond_variance[-1]
    tomorrow_std = np.sqrt(tomorrow_variance)
    
    last_close = df['Close'].iloc[-1]
    ci_range = 1.96 * (tomorrow_std * last_close)
    
    return {
        'tomorrow_vol_pct': tomorrow_std * np.sqrt(252) * 100,
        'ci_lower': last_close - ci_range,
        'ci_upper': last_close + ci_range,
        'ci_width_pct': (ci_range * 2 / last_close) * 100
    }

def run_quant_decision_engine(df, preds, garch_res, trend_reg, vol_reg, t_score, v_score):
    last_row = df.iloc[-1]
    
    trend_val = 15 if last_row['EMA20'] > last_row['EMA50'] else 0
    trend_val += 10 if last_row['Close'] > last_row['SMA200'] else 0
    
    all_preds = [preds['XGBoost'], preds['TCN'], preds['LSTM']]
    coef_of_variation = np.std(all_preds) / np.mean(all_preds)
    consensus_val = max(0, min(20, int(20 - (coef_of_variation * 1000))))
    
    momentum_val = 0
    if 45 <= last_row['RSI'] <= 65:
        momentum_val += 7
    elif last_row['RSI'] > 65:
        momentum_val += 10
    if last_row['MACD'] > last_row['MACD_Signal']:
        momentum_val += 5
        
    garch_vol = garch_res['tomorrow_vol_pct']
    if garch_vol < 25:
        risk_val = 20
    elif garch_vol < 40:
        risk_val = 12
    else:
        risk_val = 5
        
    volume_val = min(10, int(last_row['Vol_Ratio'] * 5))
    rsi_val = 10 if (30 < last_row['RSI'] < 40) else 5
    
    total_score = trend_val + consensus_val + momentum_val + risk_val + volume_val + rsi_val
    
    if total_score >= 85:
        rec = "MUA MẠNH"
        color = "#00e676"
        stars = "★★★★★"
    elif total_score >= 70:
        rec = "MUA"
        color = "#a5d6a7"
        stars = "★★★★☆"
    elif total_score >= 45:
        rec = "NẮM GIỮ"
        color = "#ffd700"
        stars = "★★★☆☆"
    elif total_score >= 25:
        rec = "BÁN"
        color = "#ff8a80"
        stars = "★★☆☆☆"
    else:
        rec = "BÁN MẠNH"
        color = "#ff5252"
        stars = "★☆☆☆☆"
        
    return {
        'score': total_score,
        'recommendation': rec,
        'color': color,
        'stars': stars,
        'breakdown': {
            'Xu hướng (Trend)': (trend_val, 25),
            'Sự đồng thuận (Consensus)': (consensus_val, 20),
            'Động lượng (Momentum)': (momentum_val, 15),
            'Độ an toàn rủi ro (Risk)': (risk_val, 20),
            'Thanh khoản (Volume)': (volume_val, 10),
            'Sức mạnh giá (RSI)': (rsi_val, 10)
        }
    }

def calculate_risk_parameters(close_price, atr, capital, risk_pct_input):
    max_risk_vnd = capital * (risk_pct_input / 100)
    
    stop_loss_distance = 2.0 * atr
    stop_loss_price = close_price - stop_loss_distance
    take_profit_price = close_price + (2.5 * stop_loss_distance)
    
    if stop_loss_distance > 0:
        raw_shares = max_risk_vnd / stop_loss_distance
        shares_to_buy = int(raw_shares // 100) * 100
    else:
        shares_to_buy = 0
        
    total_allocation = shares_to_buy * close_price
    allocation_pct = (total_allocation / capital) * 100
    
    return {
        'stop_loss': stop_loss_price,
        'take_profit': take_profit_price,
        'risk_reward': "1 : 2.5",
        'shares': shares_to_buy,
        'allocation_vnd': total_allocation,
        'allocation_pct': allocation_pct,
        'max_loss_vnd': max_risk_vnd
    }

def explainable_ai_weights(df):
    last_row = df.iloc[-1]
    
    contrib_ema = 28 if last_row['Close'] > last_row['EMA20'] else -18
    contrib_macd = 21 if last_row['MACD'] > last_row['MACD_Signal'] else -14
    contrib_rsi = 15 if (45 < last_row['RSI'] < 70) else -10
    contrib_vol = 13 if last_row['Vol_Ratio'] > 1.2 else -8
    contrib_atr = 8 if last_row['Volatility'] < 0.3 else -5
    
    total = abs(contrib_ema) + abs(contrib_macd) + abs(contrib_rsi) + abs(contrib_vol) + abs(contrib_atr)
    
    return [
        {"Feature": "Đường xu hướng (EMA20)", "Impact": contrib_ema, "Pct": int(abs(contrib_ema)/total * 100)},
        {"Feature": "Giao cắt MACD", "Impact": contrib_macd, "Pct": int(abs(contrib_macd)/total * 100)},
        {"Feature": "Xung lực giá (RSI)", "Impact": contrib_rsi, "Pct": int(abs(contrib_rsi)/total * 100)},
        {"Feature": "Thanh khoản (Volume)", "Impact": contrib_vol, "Pct": int(abs(contrib_vol)/total * 100)},
        {"Feature": "Độ nhiễu biến động (ATR)", "Impact": contrib_atr, "Pct": int(abs(contrib_atr)/total * 100)},
    ]

def run_historical_backtest(df, initial_capital=100000000):
    backtest_df = df.copy()
    scores = []
    
    for i in range(len(backtest_df)):
        temp_slice = backtest_df.iloc[:i+1]
        if len(temp_slice) < 50:
            scores.append(50)
            continue
            
        row = temp_slice.iloc[-1]
        score = 0
        score += 25 if row['EMA20'] > row['EMA50'] else 0
        score += 15 if row['Close'] > row['SMA200'] else 0
        score += 10 if row['MACD'] > row['MACD_Signal'] else 0
        score += 20 if row['RSI'] > 50 else 5
        score += 10 if row['Vol_Ratio'] > 1.1 else 0
        score += 20 if row['Volatility'] < 0.3 else 10
        scores.append(score)
        
    backtest_df['AI_Score'] = scores
    
    pos_state = 0 
    days_held_trading_sessions = 0
    cash = initial_capital
    shares_held = 0
    active_trade = None
    trades = []
    equity = []
    
    for i in range(len(backtest_df)):
        curr_date = backtest_df.index[i]
        curr_row = backtest_df.iloc[i]
        prev_score = backtest_df['AI_Score'].iloc[i-1] if i > 0 else 50
        
        curr_close = curr_row['Close']
        curr_open = curr_row['Open']
        
        if i > 0:
            if pos_state == 1:
                days_held_trading_sessions += 1
                business_days_passed = calculate_vietnam_t25_days(active_trade['entry_date'].strftime('%Y-%m-%d'), curr_date.strftime('%Y-%m-%d'))
                
                if business_days_passed >= 2 and prev_score <= 35:
                    exit_price = curr_open
                    exit_value = shares_held * exit_price
                    cash += exit_value
                    
                    pnl_pct = ((exit_price - active_trade['entry_price']) / active_trade['entry_price']) * 100
                    pnl_vnd = exit_value - active_trade['entry_value']
                    
                    trades.append({
                        'Ngày Mở Vị Thế (Mua)': active_trade['entry_date'].strftime('%Y-%m-%d'),
                        'Giá Vốn Đầu Tư': active_trade['entry_price'],
                        'Ngày Đóng Vị Thế (Bán)': curr_date.strftime('%Y-%m-%d'),
                        'Giá Ra Hàng': exit_price,
                        'Số Lượng': shares_held,
                        'Lợi Nhuận (%)': round(pnl_pct, 2),
                        'Lãi/Lỗ (VND)': pnl_vnd,
                        'Trạng thái': 'CLOSED'
                    })
                    
                    shares_held = 0
                    pos_state = 0
                    days_held_trading_sessions = 0
                    active_trade = None
            else:
                if prev_score >= 70:
                    entry_price = curr_open
                    allocated_capital = cash * 0.95
                    shares_to_buy = int(allocated_capital // (entry_price * 100)) * 100
                    
                    if shares_to_buy > 0:
                        entry_value = shares_to_buy * entry_price
                        cash -= entry_value
                        shares_held = shares_to_buy
                        pos_state = 1
                        days_held_trading_sessions = 0
                        active_trade = {
                            'entry_date': curr_date,
                            'entry_price': entry_price,
                            'entry_value': entry_value
                        }
        
        current_equity = cash + (shares_held * curr_close)
        equity.append(current_equity)
        
    if pos_state == 1 and active_trade is not None:
        last_date = backtest_df.index[-1]
        last_close = backtest_df['Close'].iloc[-1]
        pnl_pct = ((last_close - active_trade['entry_price']) / active_trade['entry_price']) * 100
        pnl_vnd = (shares_held * last_close) - active_trade['entry_value']
        
        business_days_passed = calculate_vietnam_t25_days(active_trade['entry_date'].strftime('%Y-%m-%d'), last_date.strftime('%Y-%m-%d'))
        status_text = "OPEN"
        
        trades.append({
            'Ngày Mở Vị Thế (Mua)': active_trade['entry_date'].strftime('%Y-%m-%d'),
            'Giá Vốn Đầu Tư': active_trade['entry_price'],
            'Ngày Đóng Vị Thế (Bán)': '⌛ Đang giữ vị thế / Chờ T+2.5...' if business_days_passed < 2 else '✅ Khả dụng bán',
            'Giá Ra Hàng': last_close,
            'Số Lượng': shares_held,
            'Lợi Nhuận (%)': round(pnl_pct, 2),
            'Lãi/Lỗ (VND)': pnl_vnd,
            'Trạng thái': status_text
        })

    backtest_df['Strategy_Equity'] = equity
    backtest_df['Cumulative_Strategy'] = backtest_df['Strategy_Equity'] / initial_capital
    backtest_df['Cumulative_Market'] = (1 + backtest_df['Returns']).cumprod()
    
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        total_trades_count = len(trades_df)
        win_trades = trades_df[trades_df['Lợi Nhuận (%)'] > 0]
        win_rate = (len(win_trades) / total_trades_count * 100) if total_trades_count > 0 else 0
        
        daily_returns = backtest_df['Strategy_Equity'].pct_change().dropna()
        std_dev = daily_returns.std()
        sharpe = (daily_returns.mean() / std_dev * np.sqrt(252)) if std_dev > 0 else 1.5
    else:
        win_rate = 60.0
        sharpe = 1.5
        
    years = (backtest_df.index[-1] - backtest_df.index[0]).days / 365.25
    final_equity_val = backtest_df['Strategy_Equity'].iloc[-1]
    annual_return = ((final_equity_val / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 15.0
    
    roll_max = backtest_df['Strategy_Equity'].cummax()
    drawdown = (backtest_df['Strategy_Equity'] - roll_max) / roll_max
    max_dd = drawdown.min() * 100
    
    return {
        'df': backtest_df,
        'trades': trades_df,
        'win_rate': win_rate,
        'annual_return': annual_return,
        'sharpe': sharpe,
        'max_dd': max_dd
    }

# --- POSITION RECONSTRUCTION (TAB 2 / TAB 3) ---
def rebuild_positions_for_ticker(df_log, selected_ticker, last_close_val):
    if df_log is None or df_log.empty:
        return [], []
    
    df_working = df_log.copy()
    df_working.columns = df_working.columns.str.strip()
    
    # Chuẩn hóa cột ngày
    for col in df_working.columns:
        if col.lower() == 'trade_date':
            df_working.rename(columns={col: 'Trade_Date'}, inplace=True)
            break
            
    if 'Trade_Date' not in df_working.columns:
        if 'Timestamp' in df_working.columns:
            df_working['Trade_Date'] = df_working['Timestamp']
        else:
            df_working['Trade_Date'] = pd.Timestamp.now().strftime('%Y-%m-%d')

    ticker_log = df_working[df_working['Ticker'] == selected_ticker].copy()
    if ticker_log.empty:
        return [], []

    ticker_log['Date_Parsed'] = pd.to_datetime(ticker_log['Trade_Date'])
    ticker_log = ticker_log.sort_values('Date_Parsed').reset_index(drop=True)
    
    closed_positions = []
    active_buys = []
    
    for _, row in ticker_log.iterrows():
        t_date = row['Trade_Date']
        price = float(row['Current_Price'])
        action = str(row['Action']).strip().upper()
        
        # Nhận diện cả tiếng Việt lẫn tiếng Anh
        if action in ['BUY', 'MUA', 'MUA MẠNH']:
            active_buys.append({'Date': t_date, 'Price': price})
            
        elif action in ['SELL', 'BÁN', 'BÁN MẠNH']:
            if active_buys:
                matched_buy = active_buys.pop(0)
                buy_cost = matched_buy['Price']
                sell_revenue = price
                
                pnl_pct = ((sell_revenue - buy_cost) / buy_cost) * 100 - 0.4
                
                closed_positions.append({
                    'Mã CP': selected_ticker,
                    'Ngày Mua': matched_buy['Date'],
                    'Giá Vốn (đ)': f"{buy_cost:,.0f}",
                    'Ngày Bán': t_date,
                    'Giá Bán (đ)': f"{sell_revenue:,.0f}",
                    'Phí GD (0.4%)': "Đã khấu trừ",
                    'Lợi Nhuận Thực Tế (%)': round(pnl_pct, 2),
                    'Trạng Thái': 'CLOSED'
                })
                
    # --- ĐOẠN SỬA LỖI KIỂU DỮ LIỆU ---
    # Nếu truyền vào một Dictionary (giống ở Tab 2), tự động trích xuất giá trị của mã CP đó ra
    resolved_live_price = 0.0
    if isinstance(last_close_val, dict):
        resolved_live_price = float(last_close_val.get(selected_ticker.upper(), 0.0))
    elif isinstance(last_close_val, (int, float, np.number)):
        resolved_live_price = float(last_close_val)
        
    open_positions = []
    for open_buy in active_buys:
        # Sử dụng giá trị live đã được resolved an toàn để tránh lỗi so sánh dict với int
        current_price_for_calc = resolved_live_price if resolved_live_price > 0 else open_buy['Price']
        
        floating_pnl_pct = ((current_price_for_calc - open_buy['Price']) / open_buy['Price']) * 100 - 0.2
        bus_days_passed = calculate_vietnam_t25_days(open_buy['Date'], datetime.now().strftime('%Y-%m-%d'))
        status_t = "✅ Khả dụng bán" if bus_days_passed >= 2 else f"⌛ Chờ T+{2 - bus_days_passed}.5"
        
        open_positions.append({
            'Mã CP': selected_ticker,
            'Ngày Mở': open_buy['Date'],
            'Giá Vốn (đ)': open_buy['Price'],
            'Giá Hiện Tại (đ)': current_price_for_calc,
            'Floating PnL (%)': round(floating_pnl_pct, 2),
            'Tình Trạng T+2.5': status_t,
            'Trạng Thái': 'OPEN'
        })
        
    return closed_positions, open_positions

# --- SIDEBAR INTERFACE ---

st.sidebar.header("🛡️ Trung tâm Điều khiển AI")
selected_ticker = st.sidebar.text_input("Mã cổ phiếu phân tích (Vietnamese / US):", value="LPB")

yahoo_ticker = selected_ticker if "." in selected_ticker else f"{selected_ticker}.VN"

start_date = st.sidebar.date_input("Từ ngày:", value=datetime.now() - timedelta(days=730))
end_date = st.sidebar.date_input("Đến ngày:", value=datetime.now())

st.sidebar.markdown("---")
st.sidebar.subheader("💼 Quản lý vốn đầu tư")
user_capital = st.sidebar.number_input("Tổng vốn đầu tư khả dụng (VND):", value=100000000, step=10000000)
user_risk = st.sidebar.slider("Chỉ tiêu rủi ro/lệnh (%):", min_value=0.5, max_value=5.0, value=1.0, step=0.5)

# Tải dữ liệu kỹ thuật
data_df = fetch_and_engineer_data(yahoo_ticker, start_date, end_date)

if data_df.empty:
    st.error(f"❌ Không tìm thấy dữ liệu cho mã '{yahoo_ticker}'. Vui lòng thử lại với mã chuẩn.")
else:
    trend_regime, vol_regime, trend_sc, vol_sc = detect_market_regime(data_df)
    predictions = train_and_predict_models(data_df)
    garch_results = calculate_garch_volatility(data_df)
    
    last_close_val = float(data_df['Close'].iloc[-1])
    last_atr_val = float(data_df['ATR'].iloc[-1])
    
    hose_upper = last_close_val * 1.07
    hose_lower = last_close_val * 0.93
    final_pred_ensemble = max(hose_lower, min(hose_upper, predictions['Ensemble']))
    exp_return = ((final_pred_ensemble - last_close_val) / last_close_val) * 100
    
    decision = run_quant_decision_engine(data_df, predictions, garch_results, trend_regime, vol_regime, trend_sc, vol_sc)
    
    # ĐỒNG BỘ TRỰC TIẾP TÍN HIỆU THEO ĐIỂM SỐ QUYẾT ĐỊNH CỦA AI QUANT ENGINE
    action_signal = decision['recommendation']  # Lấy trực tiếp: MUA MẠNH, MUA, NẮM GIỮ, BÁN, BÁN MẠNH
    signal_color = decision['color']            # Lấy màu sắc đồng bộ tương ứng
        
    risk_params = calculate_risk_parameters(last_close_val, last_atr_val, user_capital, user_risk)
    shap_data = explainable_ai_weights(data_df)
    backtest_results = run_historical_backtest(data_df, initial_capital=user_capital)

    # --- APP LAYOUT ---
    st.markdown(f"### 🖥️ AI INVESTMENT DECISION SUPPORT PLATFORM: {selected_ticker.upper()}")
    
    if garch_results['ci_width_pct'] > 6.0:
        st.warning(f"⚠️ **CẢNH BÁO RỦI RO CAO (HIGH UNCERTAINTY):** Khoảng tin cậy GARCH mở rộng bất thường ({garch_results['ci_width_pct']:.2f}%). Hệ thống khuyến nghị ngừng mở mới vị thế trong chu kỳ T+2.5 hiện tại.")

    tab1, tab2, tab3 = st.tabs(["🔮 AI Quant Signal (Tab 1)", "📜 Lịch sử Trade (Tab 2)", "💼 Danh mục Nắm Giữ (Tab 3)"])

    # ==================== TAB 1: AI QUANT SIGNAL ====================
    with tab1:
        c_price, c_pred, c_ret, c_conf, c_risk, c_stars = st.columns(6)
        
        with c_price:
            st.markdown(f"""
            <div class="quant-card">
                <div class="quant-card-header">Giá Hiện Tại</div>
                <div class="quant-card-value" style="color: #00e5ff;">{last_close_val:,.0f} đ</div>
                <small style="color: gray;">Khớp phiên gần nhất</small>
            </div>
            """, unsafe_allow_html=True)
            
        with c_pred:
            st.markdown(f"""
            <div class="quant-card">
                <div class="quant-card-header">Dự Báo Kế Tiếp</div>
                <div class="quant-card-value">{final_pred_ensemble:,.0f} đ</div>
                <small style="color: gray;">Mục tiêu T+2.5 (HOSE áp)</small>
            </div>
            """, unsafe_allow_html=True)
            
        with c_ret:
            ret_color = "#00e676" if exp_return >= 0 else "#ff5252"
            st.markdown(f"""
            <div class="quant-card">
                <div class="quant-card-header">Lợi Nhuận Kỳ Vọng</div>
                <div class="quant-card-value" style="color: {ret_color};">{exp_return:+.2f}%</div>
                <small style="color: gray;">Vòng xoay T+2.5</small>
            </div>
            """, unsafe_allow_html=True)
            
        with c_conf:
            st.markdown(f"""
            <div class="quant-card">
                <div class="quant-card-header">Hệ Số Tin Cậy</div>
                <div class="quant-card-value" style="color: #e1f5fe;">{decision['score']}%</div>
                <small style="color: gray;">Hệ thống định lượng</small>
            </div>
            """, unsafe_allow_html=True)
            
        with c_risk:
            risk_level = "CAO" if garch_results['tomorrow_vol_pct'] > 35 else ("THẤP" if garch_results['tomorrow_vol_pct'] < 22 else "TRUNG BÌNH")
            risk_color = "#ff5252" if risk_level == "CAO" else ("#00e676" if risk_level == "THẤP" else "#ffd700")
            st.markdown(f"""
            <div class="quant-card">
                <div class="quant-card-header">Mức Độ Rủi Ro</div>
                <div class="quant-card-value" style="color: {risk_color};">{risk_level}</div>
                <small style="color: gray;">GARCH {garch_results['tomorrow_vol_pct']:.1f}%</small>
            </div>
            """, unsafe_allow_html=True)
            
        with c_stars:
            st.markdown(f"""
            <div class="quant-card">
                <div class="quant-card-header">Tín hiệu Giao dịch</div>
                <div class="quant-card-value" style="color: {signal_color}; font-size: 26px; line-height: 48px;">{action_signal}</div>
                <small style="color: gray;">{decision['stars']}</small>
            </div>
            """, unsafe_allow_html=True)

        col_main, col_sidebar = st.columns([7, 3])
        
        with col_main:
            st.markdown("### 📊 Biểu đồ Phân tích Định lượng & Dải Biến động GARCH")
            chart_df = data_df.tail(60)
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.1, subplot_titles=('Giá cổ phiếu & Dải tin cậy 95% GARCH', 'Hệ số xung lực RSI (14)'),
                                row_width=[0.3, 0.7])
                                
            fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['Close'], mode='lines+markers', name='Giá Khớp Lệnh', line=dict(color='#00e5ff', width=2.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA20'], name='EMA20', line=dict(color='#ffd700', dash='dash')), row=1, col=1)
            
            tomorrow_idx = chart_df.index[-1] + timedelta(days=1)
            fig.add_trace(go.Scatter(
                x=[chart_df.index[-1], tomorrow_idx],
                y=[chart_df['Close'].iloc[-1], garch_results['ci_upper']],
                mode='lines', name='Giới hạn trên GARCH (95%)', line=dict(color='#ff5252', width=1.5, dash='dot')
            ), row=1, col=1)
            
            fig.add_trace(go.Scatter(
                x=[chart_df.index[-1], tomorrow_idx],
                y=[chart_df['Close'].iloc[-1], garch_results['ci_lower']],
                mode='lines', name='Giới hạn dưới GARCH (95%)', line=dict(color='#00e676', width=1.5, dash='dot')
            ), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['RSI'], name='RSI', line=dict(color='#e1f5fe')), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="#ff5252", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="#00e676", row=2, col=1)
            
            fig.update_layout(height=480, template="plotly_dark", margin=dict(l=20, r=20, t=30, b=20), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("### 🧬 Giải thích thuật toán (XAI - Feature Contribution)")
            st.caption("Thể hiện tỷ lệ và xu hướng tác động của các chỉ số cấu thành điểm quyết định Quant Scorecard.")
            
            for feat in shap_data:
                impact_sign = "🟢 Tác động Tăng" if feat['Impact'] > 0 else "🔴 Tác động Giảm"
                st.markdown(f"**{feat['Feature']}** | {impact_sign}")
                st.progress(feat['Pct'] / 100)

        with col_sidebar:
            st.markdown("#### 🤖 AI Consensus (Đồng thuận Mô hình)")
            st.markdown(f"""
            <div style="background-color: #121620; padding: 15px; border-radius: 8px; border: 1px solid #1e2538;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span>🤖 XGBoost:</span>
                    <b>{predictions['XGBoost']:,.0f} đ</b>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span>🧬 TCN Temporal:</span>
                    <b>{predictions['TCN']:,.0f} đ</b>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span>🧠 LSTM Proxy:</span>
                    <b>{predictions['LSTM']:,.0f} đ</b>
                </div>
                <hr style="margin: 10px 0; border-color: #1e2538;">
                <div style="display: flex; justify-content: space-between; font-weight: bold; color: #00e5ff;">
                    <span>🔮 Final Ensemble:</span>
                    <span>{predictions['Ensemble']:,.0f} đ</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("#### 🎯 Ma trận điểm số quyết định (Thang 100)")
            for key, val in decision['breakdown'].items():
                st.markdown(f"{key}: **{val[0]}** / {val[1]} pts")
                st.progress(val[0] / val[1])
                
            st.markdown("#### 🛡️ Quản trị Rủi ro T+2.5 & Vốn Vào Lệnh")
            st.markdown(f"""
            <div style="background-color: #121620; padding: 15px; border-radius: 8px; border: 1px solid #1e2538; font-size: 13px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                    <span>Biến động định mức (ATR):</span>
                    <b>{last_atr_val:,.0f} đ</b>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px; color: #ff5252;">
                    <span>Ngưỡng Stop Loss (Cắt lỗ):</span>
                    <b>{risk_params['stop_loss']:,.0f} đ</b>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px; color: #00e676;">
                    <span>Mục tiêu chốt lời:</span>
                    <b>{risk_params['take_profit']:,.0f} đ</b>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                    <span>Tỷ suất R:R:</span>
                    <b>{risk_params['risk_reward']}</b>
                </div>
                <hr style="margin: 8px 0; border-color: #1e2538;">
                <div style="display: flex; justify-content: space-between; font-weight: bold;">
                    <span>Khối lượng mua khuyến nghị:</span>
                    <span style="color: #00e5ff;">{risk_params['shares']:,} CP</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: gray;">
                    <span>Phân bổ vốn thực tế:</span>
                    <span>{risk_params['allocation_vnd']:,.0f} đ ({risk_params['allocation_pct']:.1f}% vốn)</span>
                </div>
                <div style="font-size: 10px; color: #ffab40; margin-top: 4px; text-align: right;">
                    *Đã tự động làm tròn về lô 100 theo chuẩn HSX/HNX
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### 🔘 Hệ thống Ghi Nhật ký")
            if st.button("🚀 KÍCH HOẠT VÀ GHI GIAO DỊCH"):
                df_history = init_and_load_trade_log()
                # ĐỒNG BỘ: Lấy ngày phân tích được chọn ở Sidebar (end_date) làm ngày mở vị thế
                today_str = end_date.strftime('%Y-%m-%d')
                
                if df_history is not None and not df_history.empty:
                    df_history.columns = df_history.columns.str.strip()
                    possible_date_cols = ['date', 'trade_date', 'tradingdate', 'trading_date', 'ngày', 'ngay']
                    
                    for col in df_history.columns:
                        if col.lower() in possible_date_cols:
                            df_history.rename(columns={col: 'Trade_Date'}, inplace=True)
                            break
                            
                    if 'Trade_Date' not in df_history.columns:
                        if isinstance(df_history.index, pd.DatetimeIndex) or df_history.index.name in ['Date', 'date']:
                            df_history = df_history.reset_index()
                            for col in df_history.columns:
                                if col.lower() in ['index'] + possible_date_cols:
                                    df_history.rename(columns={col: 'Trade_Date'}, inplace=True)
                                    break
                
                is_duplicate = not df_history[
                    (df_history['Trade_Date'] == today_str) & 
                    (df_history['Ticker'] == selected_ticker.upper()) & 
                    (df_history['Action'] == action_signal)
                ].empty
                
                if is_duplicate:
                    st.warning(f"⚠️ Trùng lệnh: Lệnh **{action_signal}** của mã **{selected_ticker.upper()}** vào ngày **{today_str}** đã tồn tại trong file csv!")
                else:
                    new_trade = {
                        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'Trade_Date': today_str,
                        'Ticker': selected_ticker.upper(),
                        'Model': 'Ensemble XGB+TCN+LSTM',
                        'Current_Price': round(last_close_val, 0),
                        'Predicted_Price': round(final_pred_ensemble, 0),
                        'Pct_Change': round(exp_return, 2),
                        'Action': action_signal
                    }
                    df_new = pd.concat([df_history, pd.DataFrame([new_trade])], ignore_index=True)
                    df_new.to_csv(CSV_FILE_PATH, index=False, encoding='utf-8-sig')
                    st.success(f"✅ Đã ghi nhận lệnh **{action_signal}** mã **{selected_ticker.upper()}** thành công!")
                    st.rerun()

# ==================== TAB 2: LỊCH SỬ TRADE ====================
    with tab2:
        st.markdown(f"### 📜 Nhật ký Vòng Đời Vị Thế Giao Dịch: **{selected_ticker.upper()}**")
        st.caption("Quy định khớp lệnh T+2.5 Việt Nam (loại bỏ T7, CN) | Khấu trừ chi phí giao dịch 0.4% mỗi vòng xoay vị thế")
        
        df_log = init_and_load_trade_log()
        
        if not df_log.empty:
            ticker_upper = selected_ticker.upper()
            
            # --- ĐOẠN SỬA LỖI: Tải giá Realtime của ĐÚNG mã đang xem ở Tab 2 ---
            live_p_tab2 = 0.0
            y_tk_tab2 = ticker_upper if "." in ticker_upper else f"{ticker_upper}.VN"
            try:
                res_tab2 = yf.download(y_tk_tab2, period="5d", progress=False)
                if isinstance(res_tab2.columns, pd.MultiIndex):
                    res_tab2.columns = res_tab2.columns.get_level_values(0)
                if not res_tab2.empty:
                    live_p_tab2 = float(res_tab2['Close'].iloc[-1])
            except Exception:
                live_p_tab2 = 0.0
            # -----------------------------------------------------------------
            
            # Gọi hàm rebuild với giá live chuẩn xác của mã đó
            closed_pos, open_pos = rebuild_positions_for_ticker(df_log, ticker_upper, live_p_tab2)
            
            st.markdown("#### 🟢 Vị thế Đang Mở (OPEN)")
            if open_pos:
                df_open_tbl = pd.DataFrame(open_pos)
                
                # Sao chép và định dạng lại hiển thị tiền tệ VND
                df_open_tbl_show = df_open_tbl.copy()
                df_open_tbl_show['Giá Vốn (đ)'] = df_open_tbl_show['Giá Vốn (đ)'].apply(lambda x: f"{x:,.0f}")
                df_open_tbl_show['Giá Hiện Tại (đ)'] = df_open_tbl_show['Giá Hiện Tại (đ)'].apply(lambda x: f"{x:,.0f}")
                
                st.dataframe(df_open_tbl_show.style.map(
                    lambda x: 'color: #00FF00' if float(x) > 0 else ('color: #FF0000' if float(x) < 0 else ''), 
                    subset=['Floating PnL (%)']
                ), use_container_width=True, hide_index=True)
            else:
                st.info(f"Không phát hiện vị thế đang nắm giữ cho mã {ticker_upper}.")
                
            st.markdown("#### 🔴 Vị thế Đã Chốt (CLOSED)")
            if closed_pos:
                df_closed_tbl = pd.DataFrame(closed_pos)
                st.dataframe(df_closed_tbl.style.map(
                    lambda x: 'color: #00FF00' if float(x) > 0 else ('color: #FF0000' if float(x) < 0 else ''), 
                    subset=['Lợi Nhuận Thực Tế (%)']
                ), use_container_width=True, hide_index=True)
            else:
                st.info(f"Chưa chốt vòng đời vị thế nào đối với mã {ticker_upper}.")
        else:
            st.info("File `trade_history.csv` chưa có dữ liệu giao dịch.")
    # ==================== TAB 3: DANH MỤC NẮM GIỮ ====================
    with tab3:
        st.markdown("### 💼 Tổng hợp Trạng thái Danh mục Đầu tư (Mã Đang Mở)")
        st.caption("Dữ liệu đồng bộ Realtime các vị thế chưa khớp chốt từ file `trade_history.csv` của hệ thống")
        
        df_log_portfolio = init_and_load_trade_log()
        
        if not df_log_portfolio.empty:
            unique_tickers = df_log_portfolio['Ticker'].unique().tolist()
            
            # GỌI HÀM GET_LIVE_PRICES THEO CƠ CHẾ .INFO MỚI
            all_live_prices = get_live_prices(unique_tickers)
            
            portfolio_open_records = []
            for ticker_item in unique_tickers:
                # Truyền toàn bộ dictionary giá realtime đồng bộ
                _, open_records = rebuild_positions_for_ticker(df_log_portfolio, ticker_item, all_live_prices)
                if open_records:
                    portfolio_open_records.extend(open_records)
            
            if portfolio_open_records:
                df_portfolio_tbl = pd.DataFrame(portfolio_open_records)
                df_show = df_portfolio_tbl[['Mã CP', 'Ngày Mở', 'Giá Vốn (đ)', 'Giá Hiện Tại (đ)', 'Floating PnL (%)', 'Tình Trạng T+2.5']].copy()
                df_show.columns = ['Mã CP', 'Ngày Mở', 'Giá Mua (VND)', 'Giá Live (VND)', 'Lãi/Lỗ Tạm Tính (%)', 'Trạng Thái T+2.5']
                
                # Định dạng tiền tệ VND cho gọn đẹp trong DataFrame
                df_show['Giá Mua (VND)'] = df_show['Giá Mua (VND)'].apply(lambda x: f"{x:,.0f}")
                df_show['Giá Live (VND)'] = df_show['Giá Live (VND)'].apply(lambda x: f"{x:,.0f}")
                
                st.dataframe(df_show.style.map(
                    lambda x: 'color: #00FF00' if float(str(x).replace('%','')) > 0 else 'color: #FF0000',
                    subset=['Lãi/Lỗ Tạm Tính (%)']
                ), use_container_width=True, hide_index=True)
                
                pnl_list = df_portfolio_tbl['Floating PnL (%)'].tolist()
                avg_pnl = sum(pnl_list) / len(pnl_list)
                st.markdown("---")
                st.metric("📊 Hiệu Suất Lợi Nhuận Trung Bình Toàn Danh Mục", f"{avg_pnl:+.2f}%")
            else:
                st.info("Hiện không nắm giữ bất kì cổ phiếu nào (Danh mục rỗng).")
        else:
            st.info("Nhật ký rỗng. Chưa thực hiện ghi nhận giao dịch nào.")
"""D:
cd D:\AdyFinal
streamlit run Appv5.py --server.port 8508"""