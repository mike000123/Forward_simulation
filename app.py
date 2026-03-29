from __future__ import annotations

from pathlib import Path
 
import altair as alt
import pandas as pd
import streamlit as st

from trading_platform.config import AppConfig, Mode, RiskConfig, StrategyConfig
from trading_platform.data.sources import MarketDataRequest, fetch_price_data, load_price_data_from_csv
from trading_platform.engine import TradingEngine
from trading_platform.state.storage import ensure_storage
from trading_platform.ui.themes import THEMES, apply_theme

st.set_page_config(page_title="Modular Algo Trading Platform", layout="wide")

if "theme" not in st.session_state:
    st.session_state["theme"] = "Dark Pro"

apply_theme(st.session_state["theme"])
st.title("📈 Modular Trading Platform (Paper + Live via Alpaca)")

plan_tab, app_tab = st.tabs(["Architecture & Plan", "Trading Console"])

with plan_tab:
    st.subheader("Execution Flow Design")
    st.markdown(
        """
1. **Data ingestion**: CSV upload or Yahoo Finance fetch into normalized OHLC schema (`date/open/high/low/close`).
2. **Signal generation**: strategy plugin computes indicators and emits structured signals.
3. **Risk checks**: global policy enforces leverage, position sizing, daily loss, drawdown, and SL/TP guardrails.
4. **Order routing**: mode-aware router dispatches to paper simulator or Alpaca live API.
5. **State tracking**: signals/orders/events/config snapshots are persisted to `/storage`.
6. **Reporting**: Streamlit dashboard renders signals, blocked trades, orders, and portfolio metrics.
        """
     )
 

    st.subheader("Mode Separation & Live Safeguards")
    st.markdown(
        """
- **Paper mode** is default and never sends real broker orders.
- **Live mode** requires a dedicated UI arm switch and explicit confirmation phrase.
- Missing API keys automatically block live orders.
- Risk denials are logged and displayed before any routing attempt.
        """
     )

    st.subheader("Strategy Abstraction")
    st.markdown(
        """
- All strategies implement a common interface (`generate_signals`, `parameters`).
- Current plugin: **RSI Mean Reversion**.
- Add new strategy by creating a class in `trading_platform/strategies/` and wiring it in `TradingEngine._build_strategy`.
        """
     )
 

    st.subheader("Persistence/Logging")
    st.code(
        """
storage/
  signals.csv      # generated signals
  orders.csv       # accepted routed orders
  events.log       # JSONL event stream (submitted/blocked)
  configs/last_run.json
        """.strip(),
        language="text",
     )
 

with app_tab:
    st.sidebar.header("Platform Settings")
    theme = st.sidebar.selectbox("Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state["theme"]))
    st.session_state["theme"] = theme
    apply_theme(theme)

    mode_label = st.sidebar.radio("Execution Mode", ["paper", "live"], index=0)
    mode = Mode(mode_label)

    data_source = st.sidebar.radio("Data Source", ["Ticker (Yahoo)", "CSV Upload"], index=0)
    ticker = st.sidebar.text_input("Ticker", value="AAPL").upper()
    interval = st.sidebar.selectbox("Interval", ["5m", "15m", "1h", "1d"], index=2)

    start_date = st.sidebar.date_input("Start", value=(pd.Timestamp.utcnow() - pd.Timedelta(days=120)).date())
    end_date = st.sidebar.date_input("End", value=pd.Timestamp.utcnow().date())

    st.sidebar.subheader("RSI Strategy")
    rsi_period = st.sidebar.number_input("RSI period", min_value=2, max_value=100, value=14)
    rsi_buy = st.sidebar.slider("RSI buy threshold", 5, 50, 30)
    rsi_sell = st.sidebar.slider("RSI sell threshold", 50, 95, 70)
    tp_pct = st.sidebar.number_input("Take-profit %", min_value=0.1, max_value=50.0, value=3.0)
    sl_pct = st.sidebar.number_input("Stop-loss %", min_value=0.1, max_value=20.0, value=2.0)

    st.sidebar.subheader("Risk Controls")
    capital = st.sidebar.number_input("Starting capital", min_value=100.0, value=10_000.0, step=100.0)
    max_pos = st.sidebar.slider("Max capital per trade %", 1, 100, 20)
    max_day_loss = st.sidebar.slider("Max day loss %", 1, 20, 5)
    max_dd = st.sidebar.slider("Max drawdown %", 5, 80, 20)
    max_lev = st.sidebar.slider("Max leverage", 1.0, 20.0, 5.0)

    st.sidebar.subheader("Live Safety")
    live_armed = False
    if mode == Mode.LIVE:
        st.sidebar.warning("Live mode selected. Orders can reach Alpaca if armed.")
        arm = st.sidebar.checkbox("I understand and want to arm live execution", value=False)
        phrase = st.sidebar.text_input("Type: ARM LIVE TRADING")
        live_armed = arm and phrase.strip() == "ARM LIVE TRADING"
        if not live_armed:
            st.sidebar.info("Live routing remains blocked until both safeguards are satisfied.")

    if data_source == "Ticker (Yahoo)":
        if st.button("Fetch Market Data", type="primary"):
            try:
                req = MarketDataRequest(
                    ticker=ticker,
                    interval=interval,
                    start=pd.Timestamp(start_date),
                    end=pd.Timestamp(end_date),
                )
                st.session_state["market_data"] = fetch_price_data(req)
            except Exception as exc:
                st.error(f"Failed to fetch data: {exc}")
    else:
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded is not None:
            try:
                st.session_state["market_data"] = load_price_data_from_csv(uploaded)
            except Exception as exc:
                st.error(f"CSV parse failed: {exc}")

    data = st.session_state.get("market_data")
    if data is None or data.empty:
        st.info("Load market data to continue.")
         st.stop()
 

    st.success(f"Loaded {len(data)} rows for {ticker}.")
 

    c1, c2 = st.columns([1.2, 1.0])
     with c1:

        st.subheader("Price")
        st.altair_chart(
            alt.Chart(data).mark_line().encode(x="date:T", y="close:Q", tooltip=["date:T", "close:Q"]).properties(height=280),
             use_container_width=True,
         )

    with c2:
        st.subheader("Data Preview")
        st.dataframe(data.tail(25), use_container_width=True)
 

    config = AppConfig(
        mode=mode,
        ticker=ticker,
        interval=interval,
        theme=theme,
        strategy=StrategyConfig(
            name="RSI Mean Reversion",
            params={
                "rsi_period": int(rsi_period),
                "rsi_buy_threshold": float(rsi_buy),
                "rsi_sell_threshold": float(rsi_sell),
                "take_profit_pct": float(tp_pct),
                "stop_loss_pct": float(sl_pct),
            },
        ),
        risk=RiskConfig(
            starting_capital=float(capital),
            max_capital_per_trade_pct=float(max_pos),
            max_daily_loss_pct=float(max_day_loss),
            max_drawdown_pct=float(max_dd),
            max_leverage=float(max_lev),
        ),
     )
 

    if st.button("Run Engine", type="primary"):
        engine = TradingEngine(config=config, storage_root="storage")
        result = engine.run(data, live_armed=live_armed)
        st.session_state["engine_result"] = result

    result = st.session_state.get("engine_result")
    if result:
        st.subheader("Run Output")
        m1, m2, m3 = st.columns(3)
        m1.metric("Signals", len(result.signals))
        m2.metric("Orders accepted", len(result.orders))
        m3.metric("Orders blocked", len(result.blocked))

        if result.orders:
            st.markdown("**Accepted Orders**")
            st.dataframe(pd.DataFrame(result.orders), use_container_width=True)
        if result.blocked:
            st.markdown("**Blocked Orders**")
            st.dataframe(pd.DataFrame(result.blocked), use_container_width=True)

    st.subheader("Portfolio Overview")
    storage = ensure_storage("storage")
    orders_file = Path(storage.orders_file)
    if orders_file.exists():
        orders = pd.read_csv(orders_file)
        st.write(f"Total persisted orders: **{len(orders)}**")
        if not orders.empty and "mode" in orders.columns:
            st.bar_chart(orders["mode"].value_counts())
    else:
        st.caption("No persisted orders yet. Run engine to generate paper/live events.")
