#!/usr/bin/env python3
"""
Pump.fun Trading Bot - Live Performance Dashboard
Streamlit-basiertes Dashboard für Echtzeit-Überwachung
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import time
from datetime import datetime
import os

# Konfiguration
API_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
REFRESH_INTERVAL = 5  # Sekunden

st.set_page_config(
    page_title="Pump Terminal Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS für dunkles Theme
st.markdown("""
<style>
    .stApp {
        background-color: #0a0a0a;
    }
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2a2a4a;
    }
    .win { color: #00ff88; }
    .loss { color: #ff4444; }
    .neutral { color: #888888; }
    h1, h2, h3 { color: #00d4aa !important; }
    .stMetric label { color: #888888 !important; }
    .stMetric [data-testid="stMetricValue"] { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)


def fetch_data(endpoint):
    """API-Daten abrufen"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/{endpoint}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"API Fehler: {e}")
    return None


def main():
    st.title("⚡ Pump Terminal Dashboard")
    st.caption(f"Live-Überwachung | Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')}")
    
    # Sidebar für Einstellungen
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        auto_refresh = st.checkbox("Auto-Refresh (5s)", value=True)
        if st.button("🔄 Jetzt aktualisieren"):
            st.rerun()
    
    # Daten laden
    trades_data = fetch_data("trades")
    status_data = fetch_data("auto-trading/status")
    scanner_health = fetch_data("scanner/health")
    
    if not trades_data:
        st.warning("Warte auf Daten vom Bot...")
        time.sleep(2)
        st.rerun()
        return
    
    # Trades verarbeiten
    trades = trades_data if isinstance(trades_data, list) else trades_data.get("trades", [])
    open_trades = [t for t in trades if t.get("status") == "OPEN"]
    closed_trades = [t for t in trades if t.get("status") == "CLOSED"]
    
    # Metriken berechnen
    total_pnl_sol = sum(t.get("pnl", 0) for t in closed_trades)
    winners = [t for t in closed_trades if t.get("pnl_percent", 0) > 0]
    losers = [t for t in closed_trades if t.get("pnl_percent", 0) < 0]
    win_rate = len(winners) / len(closed_trades) * 100 if closed_trades else 0
    
    # ===== HAUPT-METRIKEN =====
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("🟢 Offene Trades", len(open_trades))
    
    with col2:
        st.metric("📊 Geschlossen", len(closed_trades))
    
    with col3:
        pnl_color = "normal" if total_pnl_sol >= 0 else "inverse"
        st.metric("💰 Gesamt P&L", f"{total_pnl_sol:.4f} SOL", delta=f"{total_pnl_sol:.4f}")
    
    with col4:
        st.metric("🎯 Win Rate", f"{win_rate:.1f}%")
    
    with col5:
        is_running = status_data.get("is_running", False) if status_data else False
        st.metric("⚡ Status", "AKTIV" if is_running else "GESTOPPT")
    
    st.divider()
    
    # ===== ZWEI-SPALTEN LAYOUT =====
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        # Offene Trades Tabelle
        st.subheader("🟢 Offene Positionen")
        if open_trades:
            df_open = pd.DataFrame(open_trades)
            display_cols = ["token_symbol", "amount_sol", "price_entry", "price_current", "pnl_percent", "remaining_percent"]
            available_cols = [c for c in display_cols if c in df_open.columns]
            
            if available_cols:
                df_display = df_open[available_cols].copy()
                df_display.columns = ["Token", "Betrag", "Einstieg", "Aktuell", "P&L %", "Rest %"][:len(available_cols)]
                
                # Farbcodierung
                def color_pnl(val):
                    if isinstance(val, (int, float)):
                        if val > 0:
                            return "color: #00ff88"
                        elif val < 0:
                            return "color: #ff4444"
                    return ""
                
                st.dataframe(
                    df_display.style.applymap(color_pnl, subset=["P&L %"] if "P&L %" in df_display.columns else []),
                    use_container_width=True,
                    height=300
                )
        else:
            st.info("Keine offenen Trades")
        
        # Close Reasons Chart
        st.subheader("📌 Ausstiegsgründe")
        if closed_trades:
            reasons = {}
            for t in closed_trades:
                r = t.get("close_reason", "UNKNOWN")
                reasons[r] = reasons.get(r, 0) + 1
            
            df_reasons = pd.DataFrame(list(reasons.items()), columns=["Grund", "Anzahl"])
            df_reasons = df_reasons.sort_values("Anzahl", ascending=True)
            
            fig = px.bar(
                df_reasons,
                x="Anzahl",
                y="Grund",
                orientation="h",
                color="Anzahl",
                color_continuous_scale=["#1a1a2e", "#00d4aa"]
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#888888",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with right_col:
        # Top Gewinner
        st.subheader("🏆 Top Gewinner")
        if open_trades:
            sorted_trades = sorted(open_trades, key=lambda x: x.get("pnl_percent", 0), reverse=True)[:5]
            for t in sorted_trades:
                pnl = t.get("pnl_percent", 0)
                symbol = t.get("token_symbol", "???")
                color = "#00ff88" if pnl > 0 else "#ff4444"
                st.markdown(f"**{symbol}**: <span style='color:{color}'>{pnl:+.1f}%</span>", unsafe_allow_html=True)
        
        st.divider()
        
        # Scanner Status
        st.subheader("🔍 Scanner Status")
        if scanner_health:
            summary = scanner_health.get("summary", {})
            st.metric("Quellen", f"{summary.get('healthy', 0)}/{summary.get('total_sources', 0)}")
            st.metric("Tokens gesamt", summary.get("tokens_total", 0))
        
        st.divider()
        
        # MEGA/ULTRA Winner Stats
        st.subheader("🚀 Mega-Winner")
        mega_count = sum(1 for t in closed_trades if "MEGA" in t.get("close_reason", "") or "ULTRA" in t.get("close_reason", ""))
        st.metric("MEGA/ULTRA Exits", mega_count)
    
    st.divider()
    
    # ===== P&L VERLAUF =====
    st.subheader("📈 P&L Verlauf (geschlossene Trades)")
    if closed_trades:
        # Kumulative P&L berechnen
        df_closed = pd.DataFrame(closed_trades)
        if "pnl" in df_closed.columns:
            df_closed["cumulative_pnl"] = df_closed["pnl"].cumsum()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=df_closed["cumulative_pnl"],
                mode="lines",
                fill="tozeroy",
                line=dict(color="#00d4aa", width=2),
                fillcolor="rgba(0, 212, 170, 0.1)"
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#888888",
                xaxis_title="Trade #",
                yaxis_title="Kumulativer P&L (SOL)",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Auto-Refresh
    if auto_refresh:
        time.sleep(REFRESH_INTERVAL)
        st.rerun()


if __name__ == "__main__":
    main()
