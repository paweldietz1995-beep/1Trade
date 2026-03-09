from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import secrets
import hashlib
import httpx
import asyncio
from decimal import Decimal
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="Pump.fun Trading Terminal API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBasic()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== PRICE CACHE ==============
# Cache SOL price to avoid rate limiting
sol_price_cache = {
    "price": 150.0,
    "updated_at": None
}
PRICE_CACHE_DURATION = 60  # Cache for 60 seconds

# ============== MODELS ==============

class AuthRequest(BaseModel):
    pin: str

class AuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str

class BotSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # Capital Management
    total_budget_sol: float = 0.5
    max_trade_percent: float = 20.0  # Max 20% of budget per trade
    min_trade_sol: float = 0.01
    max_parallel_trades: int = 5
    max_trade_amount_sol: float = 0.5  # Absolute max per trade
    # Risk Management
    take_profit_percent: float = 100.0  # +100% = 2x
    stop_loss_percent: float = 25.0
    trailing_stop_enabled: bool = False
    trailing_stop_percent: float = 10.0
    max_daily_loss_percent: float = 50.0
    max_daily_loss_sol: float = 0.25  # Absolute max daily loss
    max_loss_streak: int = 3
    # Live Trading Safety
    require_confirmation: bool = True  # Require confirmation for first live trade
    first_live_trade_done: bool = False
    slippage_bps: int = 100  # Default 1% slippage
    # Token Filters (Stricter defaults)
    min_liquidity_usd: float = 5000.0
    min_volume_usd: float = 10000.0  # Increased from 1000 to 10000
    max_dev_wallet_percent: float = 15.0
    max_top10_wallet_percent: float = 50.0
    min_token_age_minutes: int = 5
    max_token_age_hours: int = 24
    min_buy_sell_ratio: float = 1.2
    # Momentum Thresholds
    min_momentum_score: int = 70
    min_volume_surge_percent: float = 150.0
    min_buyers_5m: int = 30
    # Automation
    auto_trade_enabled: bool = False
    paper_mode: bool = True
    scan_interval_seconds: int = 3  # Changed from 30 to 3 seconds
    # Advanced
    smart_wallet_tracking: bool = True
    migration_detection: bool = True
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TokenRiskAnalysis(BaseModel):
    honeypot_risk: str  # LOW, MEDIUM, HIGH
    rugpull_risk: str
    liquidity_locked: bool
    dev_wallet_percent: float
    top_holder_percent: float
    risk_score: int  # 0-100
    passed_filters: bool = False
    filter_reasons: List[str] = []

class TokenData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    address: str
    name: str
    symbol: str
    price_usd: float
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    market_cap: float
    liquidity: float
    volume_24h: float
    volume_5m: float = 0.0
    holders: int
    buyers_24h: int
    sellers_24h: int
    buyers_5m: int = 0
    sellers_5m: int = 0
    buy_sell_ratio: float
    age_hours: float
    risk_analysis: Optional[TokenRiskAnalysis] = None
    momentum_score: float = 0.0  # 0-100
    signal_strength: str = "NONE"  # NONE, WEAK, MEDIUM, STRONG
    pair_address: Optional[str] = None
    dex_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TradeOpportunity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token: TokenData
    suggested_action: str  # BUY, SELL, HOLD
    confidence: float  # 0-100
    potential_profit: float
    risk_level: str  # LOW, MEDIUM, HIGH
    reason: str
    priority: int = 0  # Higher = more urgent
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=5))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Trade(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_address: str
    token_symbol: str
    token_name: str
    pair_address: Optional[str] = None
    trade_type: str  # BUY, SELL
    amount_sol: float
    amount_tokens: float = 0.0
    price_entry: float
    price_current: float
    price_peak: float = 0.0  # For trailing stop
    price_exit: Optional[float] = None
    take_profit: float
    stop_loss: float
    trailing_stop: Optional[float] = None
    status: str = "PENDING"  # PENDING, OPEN, CLOSED, CANCELLED, FAILED
    pnl: float = 0.0
    pnl_percent: float = 0.0
    paper_trade: bool = True
    auto_trade: bool = False
    wallet_address: Optional[str] = None
    tx_signature: Optional[str] = None
    close_reason: Optional[str] = None  # TP_HIT, SL_HIT, TRAILING_STOP, MANUAL, AUTO_CLOSE
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None

class TradeCreate(BaseModel):
    token_address: str
    token_symbol: str
    token_name: str
    pair_address: Optional[str] = None
    trade_type: str
    amount_sol: float
    price_entry: float
    take_profit_percent: float
    stop_loss_percent: float
    trailing_stop_percent: Optional[float] = None
    paper_trade: bool = True
    auto_trade: bool = False
    wallet_address: Optional[str] = None
    tx_signature: Optional[str] = None

class PortfolioSummary(BaseModel):
    total_budget_sol: float
    available_sol: float
    in_trades_sol: float
    wallet_balance_sol: float = 0.0  # Actual wallet balance from RPC
    total_pnl: float
    total_pnl_percent: float
    open_trades: int
    closed_trades: int
    win_rate: float
    best_trade_pnl: float
    worst_trade_pnl: float
    daily_pnl: float
    loss_streak: int
    is_paused: bool = False
    pause_reason: Optional[str] = None

class SmartWallet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    address: str
    win_rate: float = 0.0
    total_trades: int = 0
    profit_trades: int = 0
    avg_profit_percent: float = 0.0
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tokens_bought: List[str] = []
    is_tracking: bool = True

class JupiterQuote(BaseModel):
    input_mint: str
    output_mint: str
    amount: int
    slippage_bps: int = 100
    out_amount: Optional[int] = None
    price_impact: Optional[float] = None

class SwapRequest(BaseModel):
    input_mint: str
    output_mint: str
    amount: float  # In SOL or tokens
    slippage_bps: int = 100
    wallet_address: str

# ============== HIGH-FREQUENCY MULTI-TRADE ENGINE ==============

# Trading Engine State - Enhanced for High-Capacity
auto_trading_state = {
    "is_running": False,
    "last_scan": None,
    "scan_count": 0,
    "trades_executed": 0,
    "trades_today": 0,
    "errors": [],
    "current_opportunities": [],
    "signals_processed": 0,
    "signals_per_minute": 0,
    "last_trade_time": None,
    "high_frequency_mode": True,
    "min_signal_score": 50,
    # Signal Queue
    "signal_queue": [],
    "queue_max_size": 100,
    # Performance Metrics
    "total_trades": 0,
    "winning_trades": 0,
    "losing_trades": 0,
    "total_profit": 0.0,
    "total_loss": 0.0,
    "max_drawdown": 0.0,
    "peak_equity": 0.0,
    "daily_pnl": 0.0,
    "last_reset_date": None
}

# Engine Configuration - High Capacity
ENGINE_CONFIG = {
    "scan_interval_seconds": 2,        # 2 second scans
    "max_tokens_per_scan": 200,        # Process up to 200 tokens
    "max_signals_per_scan": 100,       # Analyze top 100 signals
    "max_open_trades": 30,             # Allow up to 30 simultaneous trades
    "min_signal_score": 50,            # Minimum score to trigger trade
    "take_profit_percent": 10,         # 10% take profit
    "stop_loss_percent": 6,            # 6% stop loss
    "trailing_stop_enabled": True,
    "trailing_stop_percent": 5,        # 5% trailing stop
    "daily_loss_limit_percent": 15,    # 15% max daily loss
    "loss_streak_limit": 5,            # 5 consecutive losses
    "min_liquidity_usd": 10000,        # $10k minimum liquidity
    "min_volume_surge_percent": 50,    # 50% volume surge
    "min_buy_sell_ratio": 1.2          # 1.2x buy pressure
}

class AutoTradingStatus(BaseModel):
    is_running: bool
    last_scan: Optional[str] = None
    scan_count: int = 0
    trades_executed: int = 0
    trades_today: int = 0
    scan_interval_seconds: int = 2
    errors: List[str] = []
    current_opportunities: int = 0
    signals_processed: int = 0
    signals_per_minute: float = 0.0
    high_frequency_mode: bool = True
    # Queue
    queue_size: int = 0
    queue_max_size: int = 100
    # Performance
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    daily_pnl: float = 0.0

class SignalQueueItem(BaseModel):
    """Queued signal waiting for execution"""
    address: str
    symbol: str
    signal_score: float
    momentum_score: float
    liquidity: float
    volume_5m: float
    buy_sell_ratio: float
    price_usd: float
    pair_address: str
    queued_at: str
    priority: int  # Higher = more urgent
    expiry_seconds: int = 60  # Signal expires after 60s

class MomentumSignal(BaseModel):
    token_address: str
    token_symbol: str
    signal_type: str  # VOLUME_SURGE, BUY_PRESSURE, WALLET_GROWTH, PRICE_ACCELERATION
    strength: str  # WEAK, MEDIUM, STRONG
    value: float
    threshold: float
    triggered: bool = False
    description: str

class EnhancedTokenAnalysis(BaseModel):
    token: TokenData
    momentum_signals: List[MomentumSignal]
    combined_score: float  # 0-100
    buy_signal: bool = False
    signal_reasons: List[str] = []

def calculate_enhanced_momentum(pair: Dict, settings: BotSettings) -> tuple:
    """
    Enhanced momentum detection with multiple signal types:
    - Volume Surge Detection (volume increase > 150%)
    - Buy Pressure Detection (buyers > 30 in 60s, ratio > 1.5)
    - Wallet Growth Detection
    - Price Acceleration
    """
    signals = []
    
    # Get transaction data
    txns = pair.get("txns", {})
    txns_5m = txns.get("m5", {})
    txns_1h = txns.get("h1", {})
    txns_24h = txns.get("h24", {})
    
    buys_5m = txns_5m.get("buys", 0)
    sells_5m = txns_5m.get("sells", 0)
    buys_1h = txns_1h.get("buys", 0)
    sells_1h = txns_1h.get("sells", 0)
    buys_24h = txns_24h.get("buys", 0)
    sells_24h = txns_24h.get("sells", 0)
    
    # Get volume data
    volume = pair.get("volume", {})
    volume_5m = float(volume.get("m5", 0) or 0)
    volume_1h = float(volume.get("h1", 0) or 0)
    volume_24h = float(volume.get("h24", 0) or 0)
    
    # Get price change data
    price_change = pair.get("priceChange", {})
    price_change_5m = float(price_change.get("m5", 0) or 0)
    price_change_1h = float(price_change.get("h1", 0) or 0)
    price_change_24h = float(price_change.get("h24", 0) or 0)
    
    # Liquidity
    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    
    # ===== SIGNAL 1: VOLUME SURGE DETECTION =====
    # Check if 5m volume is significantly higher than average
    avg_5m_volume = volume_1h / 12 if volume_1h > 0 else 0
    volume_surge_percent = ((volume_5m / avg_5m_volume) - 1) * 100 if avg_5m_volume > 0 else 0
    
    volume_surge_threshold = 150  # 150% increase
    volume_surge_triggered = volume_surge_percent >= volume_surge_threshold
    
    if volume_5m > 1000:  # Minimum volume threshold
        strength = "STRONG" if volume_surge_percent >= 300 else "MEDIUM" if volume_surge_percent >= 150 else "WEAK"
        signals.append(MomentumSignal(
            token_address=pair.get("baseToken", {}).get("address", ""),
            token_symbol=pair.get("baseToken", {}).get("symbol", ""),
            signal_type="VOLUME_SURGE",
            strength=strength,
            value=round(volume_surge_percent, 1),
            threshold=volume_surge_threshold,
            triggered=volume_surge_triggered,
            description=f"Volume surge: +{volume_surge_percent:.0f}% (5m: ${volume_5m:.0f})"
        ))
    
    # ===== SIGNAL 2: BUY PRESSURE DETECTION =====
    # Check buyers > 30 in last 5 minutes and buy/sell ratio > 1.5
    buy_sell_ratio_5m = buys_5m / max(sells_5m, 1)
    buy_pressure_triggered = buys_5m >= 30 and buy_sell_ratio_5m >= 1.5
    
    strength = "STRONG" if buys_5m >= 50 and buy_sell_ratio_5m >= 2.5 else \
               "MEDIUM" if buys_5m >= 30 and buy_sell_ratio_5m >= 1.5 else "WEAK"
    
    signals.append(MomentumSignal(
        token_address=pair.get("baseToken", {}).get("address", ""),
        token_symbol=pair.get("baseToken", {}).get("symbol", ""),
        signal_type="BUY_PRESSURE",
        strength=strength,
        value=round(buy_sell_ratio_5m, 2),
        threshold=1.5,
        triggered=buy_pressure_triggered,
        description=f"Buy pressure: {buys_5m} buyers (ratio: {buy_sell_ratio_5m:.1f}x)"
    ))
    
    # ===== SIGNAL 3: WALLET GROWTH DETECTION =====
    # Compare 5m buyers to 1h average
    avg_buyers_5m = buys_1h / 12 if buys_1h > 0 else 0
    wallet_growth_percent = ((buys_5m / avg_buyers_5m) - 1) * 100 if avg_buyers_5m > 0 else 0
    wallet_growth_triggered = wallet_growth_percent >= 100 and buys_5m >= 20
    
    strength = "STRONG" if wallet_growth_percent >= 200 else "MEDIUM" if wallet_growth_percent >= 100 else "WEAK"
    
    signals.append(MomentumSignal(
        token_address=pair.get("baseToken", {}).get("address", ""),
        token_symbol=pair.get("baseToken", {}).get("symbol", ""),
        signal_type="WALLET_GROWTH",
        strength=strength,
        value=round(wallet_growth_percent, 1),
        threshold=100,
        triggered=wallet_growth_triggered,
        description=f"Wallet growth: +{wallet_growth_percent:.0f}% new buyers"
    ))
    
    # ===== SIGNAL 4: PRICE ACCELERATION =====
    # Check if price is accelerating (5m change > proportional 1h change)
    expected_5m_change = price_change_1h / 12
    price_acceleration = price_change_5m - expected_5m_change
    price_acceleration_triggered = price_change_5m > 5 and price_acceleration > 2
    
    strength = "STRONG" if price_acceleration > 10 else "MEDIUM" if price_acceleration > 5 else "WEAK"
    
    signals.append(MomentumSignal(
        token_address=pair.get("baseToken", {}).get("address", ""),
        token_symbol=pair.get("baseToken", {}).get("symbol", ""),
        signal_type="PRICE_ACCELERATION",
        strength=strength,
        value=round(price_acceleration, 2),
        threshold=2.0,
        triggered=price_acceleration_triggered,
        description=f"Price acceleration: +{price_change_5m:.1f}% in 5m"
    ))
    
    # ===== CALCULATE COMBINED SCORE =====
    base_score = 40
    
    # Volume surge bonus
    if volume_surge_triggered:
        base_score += 20 if signals[0].strength == "STRONG" else 15 if signals[0].strength == "MEDIUM" else 5
    
    # Buy pressure bonus
    if buy_pressure_triggered:
        base_score += 25 if signals[1].strength == "STRONG" else 18 if signals[1].strength == "MEDIUM" else 8
    
    # Wallet growth bonus
    if wallet_growth_triggered:
        base_score += 15 if signals[2].strength == "STRONG" else 10 if signals[2].strength == "MEDIUM" else 5
    
    # Price acceleration bonus
    if price_acceleration_triggered:
        base_score += 15 if signals[3].strength == "STRONG" else 10 if signals[3].strength == "MEDIUM" else 5
    
    # Liquidity bonus/penalty
    if liquidity >= 50000:
        base_score += 5
    elif liquidity < 5000:
        base_score -= 10
    
    combined_score = min(100, max(0, base_score))
    
    # Determine signal strength
    if combined_score >= 80:
        signal_strength = "STRONG"
    elif combined_score >= 65:
        signal_strength = "MEDIUM"
    elif combined_score >= 50:
        signal_strength = "WEAK"
    else:
        signal_strength = "NONE"
    
    # Build signal reasons
    signal_reasons = []
    for sig in signals:
        if sig.triggered:
            signal_reasons.append(sig.description)
    
    # Determine if this is a BUY signal
    strong_signals = sum(1 for s in signals if s.triggered and s.strength in ["STRONG", "MEDIUM"])
    buy_signal = strong_signals >= 2 and combined_score >= 65
    
    return (
        combined_score,
        signal_strength,
        signals,
        signal_reasons,
        buy_signal,
        buys_5m,
        sells_5m,
        volume_5m,
        price_change_5m,
        price_change_1h
    )

async def execute_auto_trade_cycle():
    """
    Execute one cycle of the high-frequency auto trading engine.
    - Scans market every 2-3 seconds
    - Processes multiple signals in parallel
    - Uses signal quality scoring for trade decisions
    """
    global auto_trading_state
    
    if not auto_trading_state["is_running"]:
        return {"executed": False, "reason": "Auto trading not running"}
    
    try:
        settings = await get_bot_settings()
        
        # Get configured thresholds
        min_signal_score = getattr(settings, 'min_signal_score', 60)
        high_frequency = auto_trading_state.get("high_frequency_mode", True)
        
        # Check if paper mode or live mode
        is_paper = settings.paper_mode
        
        # Get portfolio status
        portfolio = await get_portfolio_summary()
        
        # Check risk limits
        if portfolio.is_paused:
            return {"executed": False, "reason": portfolio.pause_reason, "risk_blocked": True}
        
        # Check max parallel trades (configurable, up to 10)
        max_trades = min(settings.max_parallel_trades, 10)
        if portfolio.open_trades >= max_trades:
            return {"executed": False, "reason": f"Max parallel trades reached ({max_trades})"}
        
        # High-frequency scan with parallel processing
        logger.info(f"🔍 Auto Trading [Scan #{auto_trading_state['scan_count']+1}]: Scanning market...")
        
        # Fetch tokens from multiple sources in parallel
        import asyncio
        pump_task = asyncio.create_task(fetch_pump_fun_tokens())
        dex_task = asyncio.create_task(fetch_dex_screener_tokens(50))
        
        pump_pairs, dex_pairs = await asyncio.gather(pump_task, dex_task)
        
        # Combine and dedupe with strict quality filters
        all_pairs = {}
        for pair in pump_pairs + dex_pairs:
            address = pair.get("baseToken", {}).get("address", "")
            liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
            volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
            
            # Quality filter: liquidity > $10k, volume > $10k for high-quality signals
            min_liq = max(settings.min_liquidity_usd, 10000)  # Minimum $10k liquidity
            if address and address not in all_pairs:
                if liquidity >= min_liq and volume_24h >= 10000:
                    all_pairs[address] = pair
        
        # Parallel signal analysis
        opportunities = []
        signals_processed = 0
        
        for address, pair in all_pairs.items():
            try:
                signals_processed += 1
                
                # Calculate enhanced momentum with signal scoring
                (
                    momentum_score, signal_strength, signals, signal_reasons, 
                    buy_signal, buys_5m, sells_5m, volume_5m, price_5m, price_1h
                ) = calculate_enhanced_momentum(pair, settings)
                
                # Calculate risk analysis
                risk_analysis = calculate_risk_analysis(pair, settings)
                
                if not risk_analysis.passed_filters:
                    continue
                
                # Age constraints
                created_at = pair.get("pairCreatedAt", 0)
                if created_at:
                    age_hours = (datetime.now(timezone.utc).timestamp() * 1000 - created_at) / (1000 * 60 * 60)
                else:
                    age_hours = 999
                
                min_age_hours = settings.min_token_age_minutes / 60
                if age_hours < min_age_hours or age_hours > settings.max_token_age_hours:
                    continue
                
                # Buy/Sell ratio check (min 1.2x buy pressure)
                buy_sell_ratio = buys_5m / max(sells_5m, 1)
                if buy_sell_ratio < settings.min_buy_sell_ratio:
                    continue
                
                # SIGNAL QUALITY SCORING (0-100)
                # Factors: momentum, liquidity, volume, buy pressure
                signal_score = 0
                
                # Momentum component (0-30 points)
                signal_score += min(30, momentum_score * 0.3)
                
                # Liquidity component (0-20 points)
                liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                if liq >= 50000: signal_score += 20
                elif liq >= 20000: signal_score += 15
                elif liq >= 10000: signal_score += 10
                
                # Volume surge component (0-25 points)
                if volume_5m > 10000: signal_score += 25
                elif volume_5m > 5000: signal_score += 20
                elif volume_5m > 1000: signal_score += 10
                
                # Buy pressure component (0-25 points)
                if buy_sell_ratio >= 3.0: signal_score += 25
                elif buy_sell_ratio >= 2.0: signal_score += 20
                elif buy_sell_ratio >= 1.5: signal_score += 15
                elif buy_sell_ratio >= 1.2: signal_score += 10
                
                # Only consider signals above minimum threshold
                if buy_signal and signal_score >= min_signal_score:
                    base_token = pair.get("baseToken", {})
                    
                    opportunity = {
                        "address": address,
                        "symbol": base_token.get("symbol", "???"),
                        "name": base_token.get("name", "Unknown"),
                        "price_usd": float(pair.get("priceUsd", 0) or 0),
                        "momentum_score": momentum_score,
                        "signal_score": signal_score,  # Combined quality score
                        "signal_strength": signal_strength,
                        "signal_reasons": signal_reasons,
                        "risk_score": risk_analysis.risk_score,
                        "liquidity": liq,
                        "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
                        "volume_5m": volume_5m,
                        "pair_address": pair.get("pairAddress"),
                        "buy_sell_ratio": buy_sell_ratio,
                        "price_change_5m": price_5m
                    }
                    opportunities.append(opportunity)
                    
            except Exception as e:
                logger.error(f"Error analyzing token {address}: {e}")
                continue
        
        # Sort by SIGNAL SCORE (quality), not just momentum
        opportunities.sort(key=lambda x: x["signal_score"], reverse=True)
        
        # Update state
        auto_trading_state["last_scan"] = datetime.now(timezone.utc).isoformat()
        auto_trading_state["scan_count"] += 1
        auto_trading_state["signals_processed"] += signals_processed
        auto_trading_state["current_opportunities"] = opportunities[:5]
        
        logger.info(f"📊 Scan complete: {signals_processed} signals processed, {len(opportunities)} opportunities found")
        
        # If no opportunities, return
        if not opportunities:
            logger.info("🔍 No trading opportunities found")
            return {"executed": False, "reason": "No opportunities found", "scan_count": auto_trading_state["scan_count"]}
        
        # Take the best opportunity
        best = opportunities[0]
        
        # Check minimum confidence
        if best["momentum_score"] < 70:
            return {"executed": False, "reason": f"Best opportunity score {best['momentum_score']} < 70"}
        
        # Calculate trade amount
        trade_amount = min(
            settings.total_budget_sol * (settings.max_trade_percent / 100),
            settings.max_trade_amount_sol,
            portfolio.available_sol
        )
        
        if trade_amount < settings.min_trade_sol:
            return {"executed": False, "reason": f"Trade amount {trade_amount} < min {settings.min_trade_sol}"}
        
        # Execute trade
        logger.info(f"🚀 Auto Trading: Executing trade for {best['symbol']} ({trade_amount} SOL)")
        
        trade_data = TradeCreate(
            token_address=best["address"],
            token_symbol=best["symbol"],
            token_name=best["name"],
            pair_address=best.get("pair_address"),
            trade_type="BUY",
            amount_sol=trade_amount,
            price_entry=best["price_usd"],
            take_profit_percent=settings.take_profit_percent,
            stop_loss_percent=settings.stop_loss_percent,
            trailing_stop_percent=settings.trailing_stop_percent if settings.trailing_stop_enabled else None,
            paper_trade=is_paper,
            auto_trade=True
        )
        
        trade = await create_trade(trade_data)
        auto_trading_state["trades_executed"] += 1
        
        return {
            "executed": True,
            "trade_id": trade.id,
            "token": best["symbol"],
            "amount": trade_amount,
            "momentum_score": best["momentum_score"],
            "signal_reasons": best["signal_reasons"],
            "paper_trade": is_paper
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Auto trading error: {error_msg}")
        auto_trading_state["errors"].append({
            "time": datetime.now(timezone.utc).isoformat(),
            "error": error_msg
        })
        # Keep only last 10 errors
        auto_trading_state["errors"] = auto_trading_state["errors"][-10:]
        return {"executed": False, "error": error_msg}

# Background task for auto trading loop
auto_trading_task = None

async def process_signal_queue():
    """
    Process queued signals when trade slots become available.
    Executes highest priority signals first.
    """
    global auto_trading_state
    
    # Get current open trades
    open_trades = await db.trades.count_documents({"status": "OPEN"})
    max_trades = ENGINE_CONFIG["max_open_trades"]
    available_slots = max_trades - open_trades
    
    if available_slots <= 0 or not auto_trading_state["signal_queue"]:
        return []
    
    executed_trades = []
    settings = await get_bot_settings()
    portfolio = await get_portfolio_summary()
    
    # Sort queue by priority (signal_score)
    auto_trading_state["signal_queue"].sort(key=lambda x: x.get("signal_score", 0), reverse=True)
    
    # Process top signals up to available slots
    now = datetime.now(timezone.utc)
    queue_to_remove = []
    
    for i, signal in enumerate(auto_trading_state["signal_queue"][:available_slots]):
        try:
            # Check if signal expired
            queued_at = datetime.fromisoformat(signal.get("queued_at", now.isoformat()))
            if (now - queued_at).total_seconds() > 60:  # Expire after 60s
                queue_to_remove.append(i)
                continue
            
            # Calculate dynamic trade size
            trade_amount = calculate_dynamic_trade_size(portfolio, settings)
            
            if trade_amount < settings.min_trade_sol:
                continue
            
            # Execute trade
            trade_data = TradeCreate(
                token_address=signal["address"],
                token_symbol=signal["symbol"],
                token_name=signal.get("name", signal["symbol"]),
                pair_address=signal.get("pair_address"),
                trade_type="BUY",
                amount_sol=trade_amount,
                price_entry=signal["price_usd"],
                take_profit_percent=ENGINE_CONFIG["take_profit_percent"],
                stop_loss_percent=ENGINE_CONFIG["stop_loss_percent"],
                trailing_stop_percent=ENGINE_CONFIG["trailing_stop_percent"] if ENGINE_CONFIG["trailing_stop_enabled"] else None,
                paper_trade=settings.paper_mode,
                auto_trade=True
            )
            
            trade = await create_trade(trade_data)
            executed_trades.append(trade)
            queue_to_remove.append(i)
            
            auto_trading_state["trades_executed"] += 1
            auto_trading_state["trades_today"] += 1
            
            logger.info(f"📈 Queue trade executed: {signal['symbol']} for {trade_amount} SOL (Score: {signal['signal_score']:.0f})")
            
        except Exception as e:
            logger.error(f"Queue trade error for {signal.get('symbol', '???')}: {e}")
            queue_to_remove.append(i)
    
    # Remove processed signals from queue
    for i in sorted(queue_to_remove, reverse=True):
        if i < len(auto_trading_state["signal_queue"]):
            auto_trading_state["signal_queue"].pop(i)
    
    return executed_trades

def calculate_dynamic_trade_size(portfolio, settings):
    """
    Dynamic capital allocation based on available balance and max trades.
    trade_size = available_balance / remaining_trade_slots
    """
    max_trades = ENGINE_CONFIG["max_open_trades"]
    open_trades = portfolio.open_trades
    remaining_slots = max(1, max_trades - open_trades)
    
    # Get wallet balance or available budget
    available = portfolio.available_sol if portfolio.wallet_balance_sol == 0 else portfolio.wallet_balance_sol
    
    # Dynamic allocation: divide available capital by remaining slots
    dynamic_size = available / remaining_slots
    
    # Apply configured limits
    max_trade = settings.total_budget_sol * (settings.max_trade_percent / 100)
    min_trade = settings.min_trade_sol
    
    # Final trade size
    trade_size = min(max_trade, max(min_trade, dynamic_size))
    
    return round(trade_size, 4)

async def update_performance_metrics(trade_result: dict):
    """Update performance metrics after trade closes"""
    global auto_trading_state
    
    pnl = trade_result.get("pnl", 0)
    
    if pnl > 0:
        auto_trading_state["winning_trades"] += 1
        auto_trading_state["total_profit"] += pnl
    else:
        auto_trading_state["losing_trades"] += 1
        auto_trading_state["total_loss"] += abs(pnl)
    
    auto_trading_state["total_trades"] += 1
    auto_trading_state["daily_pnl"] += pnl
    
    # Update drawdown
    current_equity = auto_trading_state.get("peak_equity", 0) + auto_trading_state["daily_pnl"]
    if current_equity > auto_trading_state["peak_equity"]:
        auto_trading_state["peak_equity"] = current_equity
    else:
        drawdown = (auto_trading_state["peak_equity"] - current_equity) / max(auto_trading_state["peak_equity"], 1) * 100
        if drawdown > auto_trading_state["max_drawdown"]:
            auto_trading_state["max_drawdown"] = drawdown

async def check_risk_limits(portfolio, settings) -> tuple:
    """
    Check if any risk limits are breached.
    Returns: (is_blocked, reason)
    """
    # Daily loss limit check
    daily_loss_pct = abs(auto_trading_state["daily_pnl"]) / max(settings.total_budget_sol, 0.01) * 100
    if auto_trading_state["daily_pnl"] < 0 and daily_loss_pct >= ENGINE_CONFIG["daily_loss_limit_percent"]:
        return True, f"Daily loss limit reached ({daily_loss_pct:.1f}%)"
    
    # Loss streak check
    if portfolio.loss_streak >= ENGINE_CONFIG["loss_streak_limit"]:
        return True, f"Loss streak limit reached ({portfolio.loss_streak} consecutive losses)"
    
    # Portfolio pause check
    if portfolio.is_paused:
        return True, portfolio.pause_reason
    
    return False, None

async def auto_trading_loop():
    """
    High-Frequency Multi-Trade Engine Loop
    - 2 second scan interval
    - Processes up to 200 tokens per scan
    - Manages up to 30 simultaneous trades
    - Signal queue for overflow
    - Dynamic capital allocation
    """
    global auto_trading_state
    
    logger.info("🚀 HIGH-CAPACITY TRADING ENGINE STARTED")
    logger.info(f"   - Scan interval: {ENGINE_CONFIG['scan_interval_seconds']}s")
    logger.info(f"   - Max tokens/scan: {ENGINE_CONFIG['max_tokens_per_scan']}")
    logger.info(f"   - Max open trades: {ENGINE_CONFIG['max_open_trades']}")
    logger.info(f"   - Take profit: {ENGINE_CONFIG['take_profit_percent']}%")
    logger.info(f"   - Stop loss: {ENGINE_CONFIG['stop_loss_percent']}%")
    
    scan_start_time = datetime.now(timezone.utc)
    
    while auto_trading_state["is_running"]:
        cycle_start = datetime.now(timezone.utc)
        
        try:
            settings = await get_bot_settings()
            portfolio = await get_portfolio_summary()
            
            # Check risk limits first
            is_blocked, block_reason = await check_risk_limits(portfolio, settings)
            if is_blocked:
                logger.warning(f"⚠️ Trading blocked: {block_reason}")
                await asyncio.sleep(ENGINE_CONFIG["scan_interval_seconds"])
                continue
            
            # Process signal queue first (execute waiting signals)
            queue_trades = await process_signal_queue()
            
            # Get current open trades count
            open_trades = await db.trades.count_documents({"status": "OPEN"})
            available_slots = ENGINE_CONFIG["max_open_trades"] - open_trades
            
            # Scan market for new opportunities
            logger.info(f"🔍 SCAN #{auto_trading_state['scan_count']+1} | Open: {open_trades}/{ENGINE_CONFIG['max_open_trades']} | Queue: {len(auto_trading_state['signal_queue'])}")
            
            # Parallel fetch from multiple sources
            pump_task = asyncio.create_task(fetch_pump_fun_tokens())
            dex_task = asyncio.create_task(fetch_dex_screener_tokens(100))  # Get 100 tokens
            
            try:
                pump_pairs, dex_pairs = await asyncio.gather(pump_task, dex_task, return_exceptions=True)
                pump_pairs = pump_pairs if isinstance(pump_pairs, list) else []
                dex_pairs = dex_pairs if isinstance(dex_pairs, list) else []
            except Exception as e:
                logger.error(f"Fetch error: {e}")
                pump_pairs, dex_pairs = [], []
            
            # Combine and dedupe - limit to max_tokens_per_scan
            all_pairs = {}
            for pair in pump_pairs + dex_pairs:
                if len(all_pairs) >= ENGINE_CONFIG["max_tokens_per_scan"]:
                    break
                    
                address = pair.get("baseToken", {}).get("address", "")
                if not address or address in all_pairs:
                    continue
                    
                liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
                
                # Pre-filter: liquidity > $10k
                if liquidity >= ENGINE_CONFIG["min_liquidity_usd"] and volume_24h >= 5000:
                    all_pairs[address] = pair
            
            # Parallel signal analysis
            opportunities = []
            signals_processed = 0
            
            for address, pair in all_pairs.items():
                try:
                    signals_processed += 1
                    
                    # Calculate momentum
                    (
                        momentum_score, signal_strength, signals, signal_reasons,
                        buy_signal, buys_5m, sells_5m, volume_5m, price_5m, price_1h
                    ) = calculate_enhanced_momentum(pair, settings)
                    
                    # Risk analysis
                    risk_analysis = calculate_risk_analysis(pair, settings)
                    if not risk_analysis.passed_filters:
                        continue
                    
                    # Buy/sell ratio
                    buy_sell_ratio = buys_5m / max(sells_5m, 1)
                    if buy_sell_ratio < ENGINE_CONFIG["min_buy_sell_ratio"]:
                        continue
                    
                    # Calculate SIGNAL SCORE (0-100)
                    signal_score = 0
                    liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                    
                    # Momentum (0-30)
                    signal_score += min(30, momentum_score * 0.3)
                    
                    # Liquidity (0-25)
                    if liq >= 100000: signal_score += 25
                    elif liq >= 50000: signal_score += 20
                    elif liq >= 20000: signal_score += 15
                    elif liq >= 10000: signal_score += 10
                    
                    # Volume surge (0-25)
                    if volume_5m > 20000: signal_score += 25
                    elif volume_5m > 10000: signal_score += 20
                    elif volume_5m > 5000: signal_score += 15
                    elif volume_5m > 1000: signal_score += 10
                    
                    # Buy pressure (0-20)
                    if buy_sell_ratio >= 3.0: signal_score += 20
                    elif buy_sell_ratio >= 2.0: signal_score += 15
                    elif buy_sell_ratio >= 1.5: signal_score += 12
                    elif buy_sell_ratio >= 1.2: signal_score += 8
                    
                    # Only strong signals
                    if buy_signal and signal_score >= ENGINE_CONFIG["min_signal_score"]:
                        base_token = pair.get("baseToken", {})
                        
                        opportunity = {
                            "address": address,
                            "symbol": base_token.get("symbol", "???"),
                            "name": base_token.get("name", "Unknown"),
                            "price_usd": float(pair.get("priceUsd", 0) or 0),
                            "momentum_score": momentum_score,
                            "signal_score": signal_score,
                            "signal_strength": signal_strength,
                            "signal_reasons": signal_reasons,
                            "risk_score": risk_analysis.risk_score,
                            "liquidity": liq,
                            "volume_5m": volume_5m,
                            "pair_address": pair.get("pairAddress"),
                            "buy_sell_ratio": buy_sell_ratio,
                            "price_change_5m": price_5m,
                            "queued_at": datetime.now(timezone.utc).isoformat()
                        }
                        opportunities.append(opportunity)
                        
                except Exception as e:
                    continue
            
            # Sort by signal score
            opportunities.sort(key=lambda x: x["signal_score"], reverse=True)
            
            # Update state
            auto_trading_state["last_scan"] = datetime.now(timezone.utc).isoformat()
            auto_trading_state["scan_count"] += 1
            auto_trading_state["signals_processed"] += signals_processed
            auto_trading_state["current_opportunities"] = opportunities[:10]
            
            # Calculate signals per minute
            elapsed_minutes = (datetime.now(timezone.utc) - scan_start_time).total_seconds() / 60
            if elapsed_minutes > 0:
                auto_trading_state["signals_per_minute"] = auto_trading_state["signals_processed"] / elapsed_minutes
            
            logger.info(f"📊 {len(all_pairs)} tokens scanned, {len(opportunities)} opportunities (Score >= {ENGINE_CONFIG['min_signal_score']})")
            
            # Execute trades for available slots
            trades_executed_this_cycle = 0
            
            for opp in opportunities[:available_slots]:
                try:
                    # Check if we already have a trade for this token
                    existing = await db.trades.find_one({
                        "token_address": opp["address"],
                        "status": "OPEN"
                    })
                    if existing:
                        continue
                    
                    # Calculate trade size
                    trade_amount = calculate_dynamic_trade_size(portfolio, settings)
                    
                    if trade_amount < settings.min_trade_sol:
                        continue
                    
                    # Execute trade
                    trade_data = TradeCreate(
                        token_address=opp["address"],
                        token_symbol=opp["symbol"],
                        token_name=opp["name"],
                        pair_address=opp.get("pair_address"),
                        trade_type="BUY",
                        amount_sol=trade_amount,
                        price_entry=opp["price_usd"],
                        take_profit_percent=ENGINE_CONFIG["take_profit_percent"],
                        stop_loss_percent=ENGINE_CONFIG["stop_loss_percent"],
                        trailing_stop_percent=ENGINE_CONFIG["trailing_stop_percent"] if ENGINE_CONFIG["trailing_stop_enabled"] else None,
                        paper_trade=settings.paper_mode,
                        auto_trade=True
                    )
                    
                    trade = await create_trade(trade_data)
                    trades_executed_this_cycle += 1
                    auto_trading_state["trades_executed"] += 1
                    auto_trading_state["trades_today"] += 1
                    
                    logger.info(f"✅ TRADE: {opp['symbol']} | {trade_amount} SOL | Score: {opp['signal_score']:.0f} | B/S: {opp['buy_sell_ratio']:.1f}x")
                    
                except Exception as e:
                    logger.error(f"Trade execution error: {e}")
            
            # Queue remaining opportunities
            remaining_opps = opportunities[available_slots:available_slots + 20]  # Queue up to 20
            for opp in remaining_opps:
                if len(auto_trading_state["signal_queue"]) < ENGINE_CONFIG.get("queue_max_size", 100):
                    # Don't queue duplicates
                    if not any(q["address"] == opp["address"] for q in auto_trading_state["signal_queue"]):
                        auto_trading_state["signal_queue"].append(opp)
            
            # Log cycle summary
            cycle_time = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            logger.info(f"⏱️ Cycle complete: {trades_executed_this_cycle} trades, {cycle_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Trading loop error: {e}")
            auto_trading_state["errors"].append({
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            auto_trading_state["errors"] = auto_trading_state["errors"][-10:]
        
        # Wait for next scan
        await asyncio.sleep(ENGINE_CONFIG["scan_interval_seconds"])

@api_router.post("/auto-trading/start")
async def start_auto_trading(background_tasks: BackgroundTasks):
    """Start the high-capacity multi-trade engine"""
    global auto_trading_state, auto_trading_task
    
    if auto_trading_state["is_running"]:
        return {"success": False, "message": "Auto trading already running"}
    
    # Reset daily metrics if new day
    today = datetime.now(timezone.utc).date().isoformat()
    if auto_trading_state.get("last_reset_date") != today:
        auto_trading_state["trades_today"] = 0
        auto_trading_state["daily_pnl"] = 0.0
        auto_trading_state["last_reset_date"] = today
    
    # Reset state
    auto_trading_state["is_running"] = True
    auto_trading_state["scan_count"] = 0
    auto_trading_state["trades_executed"] = 0
    auto_trading_state["signals_processed"] = 0
    auto_trading_state["signals_per_minute"] = 0.0
    auto_trading_state["errors"] = []
    auto_trading_state["signal_queue"] = []
    auto_trading_state["high_frequency_mode"] = True
    auto_trading_state["current_opportunities"] = []
    
    # Start background task
    auto_trading_task = asyncio.create_task(auto_trading_loop())
    
    logger.info("🚀 HIGH-CAPACITY TRADING ENGINE STARTED")
    return {
        "success": True, 
        "message": "High-capacity trading engine started",
        "config": {
            "scan_interval_seconds": ENGINE_CONFIG["scan_interval_seconds"],
            "max_tokens_per_scan": ENGINE_CONFIG["max_tokens_per_scan"],
            "max_open_trades": ENGINE_CONFIG["max_open_trades"],
            "take_profit_percent": ENGINE_CONFIG["take_profit_percent"],
            "stop_loss_percent": ENGINE_CONFIG["stop_loss_percent"],
            "daily_loss_limit_percent": ENGINE_CONFIG["daily_loss_limit_percent"],
            "scans_per_minute": 60 / ENGINE_CONFIG["scan_interval_seconds"]
        }
    }

@api_router.post("/auto-trading/stop")
async def stop_auto_trading():
    """Stop the auto trading engine"""
    global auto_trading_state, auto_trading_task
    
    auto_trading_state["is_running"] = False
    
    if auto_trading_task:
        auto_trading_task.cancel()
        try:
            await auto_trading_task
        except asyncio.CancelledError:
            pass
        auto_trading_task = None
    
    # Calculate final stats
    total_trades = auto_trading_state.get("total_trades", 0)
    winning = auto_trading_state.get("winning_trades", 0)
    win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
    
    logger.info("🛑 HIGH-CAPACITY TRADING ENGINE STOPPED")
    return {
        "success": True, 
        "message": "Trading engine stopped",
        "session_stats": {
            "scan_count": auto_trading_state["scan_count"],
            "signals_processed": auto_trading_state["signals_processed"],
            "trades_executed": auto_trading_state["trades_executed"],
            "trades_today": auto_trading_state.get("trades_today", 0),
            "win_rate": round(win_rate, 1),
            "daily_pnl": auto_trading_state.get("daily_pnl", 0),
            "max_drawdown": auto_trading_state.get("max_drawdown", 0)
        }
    }

@api_router.get("/auto-trading/status")
async def get_auto_trading_status():
    """Get comprehensive auto trading status with performance metrics"""
    
    # Calculate win rate
    total = auto_trading_state.get("total_trades", 0)
    winning = auto_trading_state.get("winning_trades", 0)
    win_rate = (winning / total * 100) if total > 0 else 0
    
    # Calculate average profit/loss
    avg_profit = auto_trading_state.get("total_profit", 0) / max(winning, 1)
    avg_loss = auto_trading_state.get("total_loss", 0) / max(auto_trading_state.get("losing_trades", 1), 1)
    
    return {
        "is_running": auto_trading_state["is_running"],
        "last_scan": auto_trading_state["last_scan"],
        "scan_count": auto_trading_state["scan_count"],
        "trades_executed": auto_trading_state["trades_executed"],
        "trades_today": auto_trading_state.get("trades_today", 0),
        "scan_interval_seconds": ENGINE_CONFIG["scan_interval_seconds"],
        "errors": [e.get("error", "") for e in auto_trading_state["errors"][-5:]],
        "current_opportunities": len(auto_trading_state.get("current_opportunities", [])),
        "signals_processed": auto_trading_state.get("signals_processed", 0),
        "signals_per_minute": round(auto_trading_state.get("signals_per_minute", 0), 1),
        "high_frequency_mode": auto_trading_state.get("high_frequency_mode", True),
        # Queue info
        "queue_size": len(auto_trading_state.get("signal_queue", [])),
        "queue_max_size": ENGINE_CONFIG.get("queue_max_size", 100),
        # Performance metrics
        "performance": {
            "total_trades": total,
            "winning_trades": winning,
            "losing_trades": auto_trading_state.get("losing_trades", 0),
            "win_rate": round(win_rate, 1),
            "avg_profit": round(avg_profit, 6),
            "avg_loss": round(avg_loss, 6),
            "daily_pnl": round(auto_trading_state.get("daily_pnl", 0), 6),
            "max_drawdown": round(auto_trading_state.get("max_drawdown", 0), 2)
        },
        # Engine config
        "config": {
            "max_open_trades": ENGINE_CONFIG["max_open_trades"],
            "take_profit_percent": ENGINE_CONFIG["take_profit_percent"],
            "stop_loss_percent": ENGINE_CONFIG["stop_loss_percent"],
            "daily_loss_limit_percent": ENGINE_CONFIG["daily_loss_limit_percent"],
            "min_signal_score": ENGINE_CONFIG["min_signal_score"]
        }
    }

@api_router.get("/auto-trading/opportunities")
async def get_current_opportunities():
    """Get current detected opportunities from auto trading"""
    return auto_trading_state.get("current_opportunities", [])

@api_router.get("/auto-trading/queue")
async def get_signal_queue():
    """Get current signal queue waiting for execution"""
    return {
        "queue": auto_trading_state.get("signal_queue", [])[:20],  # Return top 20
        "queue_size": len(auto_trading_state.get("signal_queue", [])),
        "max_size": ENGINE_CONFIG.get("queue_max_size", 100)
    }

@api_router.post("/auto-trading/clear-queue")
async def clear_signal_queue():
    """Clear the signal queue"""
    auto_trading_state["signal_queue"] = []
    return {"success": True, "message": "Signal queue cleared"}

# ============== CONSTANTS ==============

SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# ============== HELPER FUNCTIONS ==============

def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()

def generate_token() -> str:
    return secrets.token_urlsafe(32)

async def get_sol_price() -> float:
    """Get current SOL price with caching to avoid rate limiting"""
    global sol_price_cache
    
    now = datetime.now(timezone.utc)
    
    # Return cached price if still valid
    if sol_price_cache["updated_at"]:
        cache_age = (now - sol_price_cache["updated_at"]).total_seconds()
        if cache_age < PRICE_CACHE_DURATION:
            return sol_price_cache["price"]
    
    # Try to fetch new price
    try:
        async with httpx.AsyncClient(timeout=5.0) as client_http:
            # Try DEX Screener first (more reliable, no rate limiting)
            response = await client_http.get(
                "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112"
            )
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                if pairs:
                    # Get price from USDC pair
                    for pair in pairs:
                        if pair.get("quoteToken", {}).get("symbol") in ["USDC", "USDT"]:
                            price = float(pair.get("priceUsd", 0) or 0)
                            if price > 0:
                                sol_price_cache["price"] = price
                                sol_price_cache["updated_at"] = now
                                return price
            
            # Fallback to CoinGecko
            response = await client_http.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "solana", "vs_currencies": "usd"}
            )
            if response.status_code == 200:
                data = response.json()
                price = data.get("solana", {}).get("usd", 150.0)
                sol_price_cache["price"] = price
                sol_price_cache["updated_at"] = now
                return price
    except Exception as e:
        logger.error(f"Error fetching SOL price: {e}")
    
    # Return cached price or default
    return sol_price_cache["price"]

async def fetch_dex_screener_tokens(limit: int = 50) -> List[Dict]:
    """Fetch trending Solana tokens from DEX Screener"""
    all_pairs = []
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client_http:
            # Search for multiple queries to get diverse results
            search_queries = [
                "solana SOL",
                "raydium",
                "jupiter SOL",
                "orca solana"
            ]
            
            for query in search_queries:
                try:
                    response = await client_http.get(
                        "https://api.dexscreener.com/latest/dex/search",
                        params={"q": query}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        pairs = data.get("pairs", [])
                        
                        # Filter for Solana pairs with reasonable values
                        for p in pairs:
                            if p.get("chainId") != "solana":
                                continue
                            
                            # Filter out unrealistic liquidity (likely fake/test tokens)
                            liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                            vol = float(p.get("volume", {}).get("h24", 0) or 0)
                            
                            # Skip if liquidity is unrealistically high (>$100M for memecoins)
                            if liq > 100000000:
                                continue
                            
                            # Only include pairs with some activity
                            if liq >= 1000 or vol >= 100:
                                all_pairs.append(p)
                                
                except Exception as e:
                    logger.warning(f"Search query '{query}' failed: {e}")
                    continue
            
            # Also try token profiles for latest tokens
            try:
                response = await client_http.get(
                    "https://api.dexscreener.com/token-profiles/latest/v1"
                )
                if response.status_code == 200:
                    data = response.json()
                    solana_profiles = [p for p in data if p.get("chainId") == "solana"]
                    
                    if solana_profiles:
                        token_addresses = [p.get("tokenAddress") for p in solana_profiles[:20] if p.get("tokenAddress")]
                        
                        if token_addresses:
                            tokens_str = ",".join(token_addresses[:20])
                            detail_response = await client_http.get(
                                f"https://api.dexscreener.com/latest/dex/tokens/{tokens_str}"
                            )
                            if detail_response.status_code == 200:
                                detail_data = detail_response.json()
                                for p in detail_data.get("pairs", []):
                                    liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                                    if 1000 <= liq < 100000000:
                                        all_pairs.append(p)
            except Exception as e:
                logger.warning(f"Token profiles failed: {e}")
            
            # Deduplicate by pair address
            seen = set()
            unique_pairs = []
            for p in all_pairs:
                addr = p.get("pairAddress", "")
                if addr and addr not in seen:
                    seen.add(addr)
                    unique_pairs.append(p)
            
            # Sort by volume descending
            unique_pairs.sort(key=lambda x: float(x.get("volume", {}).get("h24", 0) or 0), reverse=True)
            
            logger.info(f"📊 Loaded {len(unique_pairs)} valid Solana pairs from DEX Screener")
            return unique_pairs[:limit]
            
    except Exception as e:
        logger.error(f"Error fetching DEX Screener data: {e}")
    return []

async def fetch_pump_fun_tokens() -> List[Dict]:
    """Fetch new tokens from Pump.fun via DEX Screener"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client_http:
            # Search for Pump.fun tokens
            response = await client_http.get(
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "pump.fun"}
            )
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                logger.info(f"🚀 Loaded {len(solana_pairs)} Pump.fun pairs")
                return solana_pairs[:30]
                
            # Alternative: Search for raydium pairs
            response = await client_http.get(
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "raydium SOL"}
            )
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                return solana_pairs[:30]
                
    except Exception as e:
        logger.error(f"Error fetching Pump.fun data: {e}")
    return []

def calculate_risk_analysis(pair: Dict, settings: BotSettings) -> TokenRiskAnalysis:
    """Calculate comprehensive risk analysis for a token"""
    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    volume = float(pair.get("volume", {}).get("h24", 0) or 0)
    price_change = float(pair.get("priceChange", {}).get("h24", 0) or 0)
    
    filter_reasons = []
    passed = True
    
    # Risk calculations
    honeypot_risk = "LOW" if liquidity > 10000 else "MEDIUM" if liquidity > 2000 else "HIGH"
    rugpull_risk = "LOW" if liquidity > 50000 else "MEDIUM" if liquidity > 5000 else "HIGH"
    liquidity_locked = liquidity > 20000
    
    # Simulated holder analysis (in production, query on-chain data)
    dev_wallet_percent = 5.0 if liquidity > 20000 else 10.0 if liquidity > 5000 else 20.0
    top_holder_percent = 25.0 if volume > 50000 else 40.0 if volume > 5000 else 60.0
    
    # Apply filters
    if liquidity < settings.min_liquidity_usd:
        passed = False
        filter_reasons.append(f"Liquidity ${liquidity:.0f} < ${settings.min_liquidity_usd:.0f}")
    
    if dev_wallet_percent > settings.max_dev_wallet_percent:
        passed = False
        filter_reasons.append(f"Dev wallet {dev_wallet_percent:.1f}% > {settings.max_dev_wallet_percent:.1f}%")
    
    if top_holder_percent > settings.max_top10_wallet_percent:
        passed = False
        filter_reasons.append(f"Top holders {top_holder_percent:.1f}% > {settings.max_top10_wallet_percent:.1f}%")
    
    if honeypot_risk == "HIGH":
        passed = False
        filter_reasons.append("High honeypot risk")
    
    # Calculate overall risk score (0-100, higher = riskier)
    risk_score = 30
    if liquidity < 5000:
        risk_score += 25
    elif liquidity < 10000:
        risk_score += 15
    if volume < 1000:
        risk_score += 20
    elif volume < 5000:
        risk_score += 10
    if abs(price_change) > 80:
        risk_score += 15
    if dev_wallet_percent > 10:
        risk_score += 10
    risk_score = min(100, max(0, risk_score))
    
    return TokenRiskAnalysis(
        honeypot_risk=honeypot_risk,
        rugpull_risk=rugpull_risk,
        liquidity_locked=liquidity_locked,
        dev_wallet_percent=dev_wallet_percent,
        top_holder_percent=top_holder_percent,
        risk_score=risk_score,
        passed_filters=passed,
        filter_reasons=filter_reasons
    )

def calculate_momentum_score(pair: Dict) -> tuple:
    """Calculate momentum score and signal strength"""
    price_change_5m = float(pair.get("priceChange", {}).get("m5", 0) or 0)
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
    price_change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
    
    txns = pair.get("txns", {})
    txns_5m = txns.get("m5", {})
    txns_1h = txns.get("h1", {})
    txns_24h = txns.get("h24", {})
    
    buys_5m = txns_5m.get("buys", 0)
    sells_5m = txns_5m.get("sells", 0)
    buys_1h = txns_1h.get("buys", 0)
    sells_1h = txns_1h.get("sells", 0)
    
    volume_5m = float(pair.get("volume", {}).get("m5", 0) or 0)
    volume_1h = float(pair.get("volume", {}).get("h1", 0) or 0)
    
    # Calculate momentum score
    score = 50  # Base score
    
    # Price momentum
    if price_change_5m > 10:
        score += 15
    elif price_change_5m > 5:
        score += 10
    elif price_change_5m > 0:
        score += 5
    elif price_change_5m < -10:
        score -= 15
    
    # Buy pressure
    buy_ratio_5m = buys_5m / max(sells_5m, 1)
    if buy_ratio_5m > 3:
        score += 20
    elif buy_ratio_5m > 2:
        score += 15
    elif buy_ratio_5m > 1.5:
        score += 10
    elif buy_ratio_5m < 0.5:
        score -= 15
    
    # Volume surge
    if volume_5m > 5000:
        score += 10
    elif volume_5m > 1000:
        score += 5
    
    # Acceleration (comparing 5m to 1h trends)
    if price_change_5m > price_change_1h / 12:  # Accelerating
        score += 10
    
    score = min(100, max(0, score))
    
    # Determine signal strength
    if score >= 80:
        signal = "STRONG"
    elif score >= 65:
        signal = "MEDIUM"
    elif score >= 50:
        signal = "WEAK"
    else:
        signal = "NONE"
    
    return score, signal, buys_5m, sells_5m, volume_5m, price_change_5m, price_change_1h

async def get_jupiter_quote(input_mint: str, output_mint: str, amount: int, slippage_bps: int = 100) -> Optional[Dict]:
    """Get swap quote from Jupiter API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            response = await client_http.get(
                "https://quote-api.jup.ag/v6/quote",
                params={
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": str(amount),
                    "slippageBps": slippage_bps,
                    "onlyDirectRoutes": False,
                    "asLegacyTransaction": False
                }
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Jupiter quote error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error getting Jupiter quote: {e}")
    return None

async def build_jupiter_swap(quote: Dict, user_public_key: str) -> Optional[str]:
    """Build swap transaction from Jupiter quote"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            response = await client_http.post(
                "https://quote-api.jup.ag/v6/swap",
                json={
                    "quoteResponse": quote,
                    "userPublicKey": user_public_key,
                    "wrapAndUnwrapSol": True,
                    "dynamicComputeUnitLimit": True,
                    "prioritizationFeeLamports": "auto"
                }
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("swapTransaction")
            else:
                logger.error(f"Jupiter swap build error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error building Jupiter swap: {e}")
    return None

# ============== AUTH ENDPOINTS ==============

@api_router.post("/auth/login", response_model=AuthResponse)
async def login(request: AuthRequest):
    """Simple PIN-based authentication for single user"""
    auth_doc = await db.auth.find_one({"type": "pin"})
    
    if not auth_doc:
        # First time login - set the PIN
        pin_hash = hash_pin(request.pin)
        await db.auth.insert_one({
            "type": "pin",
            "pin_hash": pin_hash,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        token = generate_token()
        await db.sessions.insert_one({
            "token": token,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        return AuthResponse(success=True, token=token, message="PIN set successfully")
    
    # Verify PIN
    if auth_doc["pin_hash"] == hash_pin(request.pin):
        token = generate_token()
        await db.sessions.insert_one({
            "token": token,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        return AuthResponse(success=True, token=token, message="Login successful")
    
    return AuthResponse(success=False, message="Invalid PIN")

@api_router.post("/auth/verify")
async def verify_token(token: str):
    """Verify if session token is valid"""
    session = await db.sessions.find_one({"token": token})
    return {"valid": session is not None}

@api_router.post("/auth/reset")
async def reset_pin():
    """Reset PIN (for recovery)"""
    await db.auth.delete_many({"type": "pin"})
    await db.sessions.delete_many({})
    return {"success": True, "message": "PIN reset. Set new PIN on next login."}

# ============== BOT SETTINGS ENDPOINTS ==============

@api_router.get("/bot/settings", response_model=BotSettings)
async def get_bot_settings():
    """Get current bot settings"""
    settings = await db.bot_settings.find_one({"type": "bot"}, {"_id": 0})
    if not settings:
        default_settings = BotSettings()
        doc = default_settings.model_dump()
        doc["type"] = "bot"
        doc["updated_at"] = doc["updated_at"].isoformat()
        await db.bot_settings.insert_one(doc)
        return default_settings
    
    if isinstance(settings.get("updated_at"), str):
        settings["updated_at"] = datetime.fromisoformat(settings["updated_at"])
    return BotSettings(**settings)

@api_router.put("/bot/settings", response_model=BotSettings)
async def update_bot_settings(settings: BotSettings):
    """Update bot settings"""
    doc = settings.model_dump()
    doc["type"] = "bot"
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.bot_settings.update_one(
        {"type": "bot"},
        {"$set": doc},
        upsert=True
    )
    return settings

# ============== TOKEN DISCOVERY ENGINE ==============

@api_router.get("/tokens/scan", response_model=List[TokenData])
async def scan_tokens(limit: int = 30):
    """Scan for new and trending tokens with full analysis"""
    settings = await get_bot_settings()
    
    # Fetch from multiple sources
    pump_pairs = await fetch_pump_fun_tokens()
    dex_pairs = await fetch_dex_screener_tokens(limit)
    
    # Combine and dedupe with strict filtering
    all_pairs = {}
    for pair in dex_pairs + pump_pairs:  # DEX pairs first (better quality)
        address = pair.get("baseToken", {}).get("address", "")
        if not address or address in all_pairs:
            continue
        
        # Apply strict filters
        liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        vol_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
        
        # FILTER: Skip unrealistic liquidity (>$100M for memecoins)
        if liq > 100000000:
            continue
        
        # FILTER: Minimum liquidity requirement
        if liq < settings.min_liquidity_usd and vol_24h < settings.min_volume_usd:
            continue
        
        all_pairs[address] = pair
    
    logger.info(f"📊 Processing {len(all_pairs)} tokens after filtering")
    
    tokens = []
    for address, pair in list(all_pairs.items())[:limit]:
        try:
            base_token = pair.get("baseToken", {})
            price_change = pair.get("priceChange", {})
            volume = pair.get("volume", {})
            liquidity = pair.get("liquidity", {})
            txns = pair.get("txns", {}).get("h24", {})
            
            # Calculate age
            created_at = pair.get("pairCreatedAt", 0)
            if created_at:
                age_hours = (datetime.now(timezone.utc).timestamp() * 1000 - created_at) / (1000 * 60 * 60)
            else:
                age_hours = 999
            
            # Risk analysis
            risk_analysis = calculate_risk_analysis(pair, settings)
            
            # Momentum analysis
            momentum_score, signal, buys_5m, sells_5m, volume_5m, price_5m, price_1h = calculate_momentum_score(pair)
            
            buys_24h = txns.get("buys", 1)
            sells_24h = txns.get("sells", 1)
            
            token_data = TokenData(
                address=address,
                name=base_token.get("name", "Unknown"),
                symbol=base_token.get("symbol", "???"),
                price_usd=float(pair.get("priceUsd", 0) or 0),
                price_change_5m=price_5m,
                price_change_1h=price_1h,
                price_change_24h=float(price_change.get("h24", 0) or 0),
                market_cap=float(pair.get("fdv", 0) or 0),
                liquidity=float(liquidity.get("usd", 0) or 0),
                volume_24h=float(volume.get("h24", 0) or 0),
                volume_5m=volume_5m,
                holders=int(pair.get("holders", 0) or 0),
                buyers_24h=buys_24h,
                sellers_24h=sells_24h,
                buyers_5m=buys_5m,
                sellers_5m=sells_5m,
                buy_sell_ratio=round(buys_24h / max(sells_24h, 1), 2),
                age_hours=round(age_hours, 1),
                risk_analysis=risk_analysis,
                momentum_score=momentum_score,
                signal_strength=signal,
                pair_address=pair.get("pairAddress"),
                dex_id=pair.get("dexId")
            )
            tokens.append(token_data)
        except Exception as e:
            logger.error(f"Error processing token: {e}")
            continue
    
    # Sort by momentum score
    tokens.sort(key=lambda x: x.momentum_score, reverse=True)
    return tokens

@api_router.get("/tokens/{address}", response_model=TokenData)
async def get_token_details(address: str):
    """Get detailed information about a specific token"""
    settings = await get_bot_settings()
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            response = await client_http.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{address}"
            )
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                if pairs:
                    # Get the best pair (highest liquidity)
                    pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                    
                    base_token = pair.get("baseToken", {})
                    price_change = pair.get("priceChange", {})
                    volume = pair.get("volume", {})
                    liquidity = pair.get("liquidity", {})
                    txns = pair.get("txns", {}).get("h24", {})
                    
                    created_at = pair.get("pairCreatedAt", 0)
                    age_hours = (datetime.now(timezone.utc).timestamp() * 1000 - created_at) / (1000 * 60 * 60) if created_at else 0
                    
                    risk_analysis = calculate_risk_analysis(pair, settings)
                    momentum_score, signal, buys_5m, sells_5m, volume_5m, price_5m, price_1h = calculate_momentum_score(pair)
                    
                    return TokenData(
                        address=address,
                        name=base_token.get("name", "Unknown"),
                        symbol=base_token.get("symbol", "???"),
                        price_usd=float(pair.get("priceUsd", 0) or 0),
                        price_change_5m=price_5m,
                        price_change_1h=price_1h,
                        price_change_24h=float(price_change.get("h24", 0) or 0),
                        market_cap=float(pair.get("fdv", 0) or 0),
                        liquidity=float(liquidity.get("usd", 0) or 0),
                        volume_24h=float(volume.get("h24", 0) or 0),
                        volume_5m=volume_5m,
                        holders=int(pair.get("holders", 0) or 0),
                        buyers_24h=txns.get("buys", 0),
                        sellers_24h=txns.get("sells", 0),
                        buyers_5m=buys_5m,
                        sellers_5m=sells_5m,
                        buy_sell_ratio=round(txns.get("buys", 1) / max(txns.get("sells", 1), 1), 2),
                        age_hours=round(age_hours, 1),
                        risk_analysis=risk_analysis,
                        momentum_score=momentum_score,
                        signal_strength=signal,
                        pair_address=pair.get("pairAddress"),
                        dex_id=pair.get("dexId")
                    )
    except Exception as e:
        logger.error(f"Error fetching token details: {e}")
    
    raise HTTPException(status_code=404, detail="Token not found")

# ============== TRADING OPPORTUNITIES ==============

@api_router.get("/opportunities", response_model=List[TradeOpportunity])
async def get_trading_opportunities():
    """Get AI-suggested trading opportunities based on analysis"""
    settings = await get_bot_settings()
    tokens = await scan_tokens(limit=20)
    opportunities = []
    
    for token in tokens:
        # Only consider tokens that pass all filters
        if not token.risk_analysis or not token.risk_analysis.passed_filters:
            continue
        
        # Check age constraints
        min_age_hours = settings.min_token_age_minutes / 60
        if token.age_hours < min_age_hours or token.age_hours > settings.max_token_age_hours:
            continue
        
        # Check buy/sell ratio
        if token.buy_sell_ratio < settings.min_buy_sell_ratio:
            continue
        
        # Strong momentum signals
        if token.momentum_score >= 65 and token.signal_strength in ["MEDIUM", "STRONG"]:
            confidence = min(95, token.momentum_score + (10 if token.signal_strength == "STRONG" else 0))
            
            # Calculate potential profit based on momentum
            potential_profit = min(200, token.price_change_5m * 3 + token.momentum_score * 0.5)
            
            # Determine risk level
            if token.risk_analysis.risk_score < 40:
                risk_level = "LOW"
            elif token.risk_analysis.risk_score < 60:
                risk_level = "MEDIUM"
            else:
                risk_level = "HIGH"
            
            # Build reason
            reasons = []
            if token.signal_strength == "STRONG":
                reasons.append("🚀 Strong momentum")
            if token.buy_sell_ratio > 2:
                reasons.append(f"📈 {token.buy_sell_ratio:.1f}x buy pressure")
            if token.price_change_5m > 5:
                reasons.append(f"⚡ +{token.price_change_5m:.1f}% in 5min")
            if token.volume_5m > 5000:
                reasons.append(f"💰 ${token.volume_5m:.0f} volume surge")
            
            opportunity = TradeOpportunity(
                token=token,
                suggested_action="BUY",
                confidence=round(confidence, 1),
                potential_profit=round(max(potential_profit, 20), 1),
                risk_level=risk_level,
                reason=" | ".join(reasons) if reasons else "Momentum detected",
                priority=int(token.momentum_score)
            )
            opportunities.append(opportunity)
    
    # Sort by priority (momentum score)
    opportunities.sort(key=lambda x: x.priority, reverse=True)
    return opportunities[:10]

# ============== JUPITER SWAP ENDPOINTS ==============

@api_router.post("/swap/quote")
async def get_swap_quote(request: JupiterQuote):
    """Get a swap quote from Jupiter"""
    quote = await get_jupiter_quote(
        request.input_mint,
        request.output_mint,
        request.amount,
        request.slippage_bps
    )
    
    if not quote:
        raise HTTPException(status_code=400, detail="Failed to get quote")
    
    return quote

@api_router.post("/swap/build")
async def build_swap_transaction(quote: Dict, user_public_key: str):
    """Build a swap transaction from quote"""
    tx = await build_jupiter_swap(quote, user_public_key)
    
    if not tx:
        raise HTTPException(status_code=400, detail="Failed to build transaction")
    
    return {"transaction": tx}

# ============== TRADES ENDPOINTS ==============

@api_router.post("/trades", response_model=Trade)
async def create_trade(trade_data: TradeCreate):
    """Create a new trade"""
    settings = await get_bot_settings()
    
    # Check trade limits
    open_trades = await db.trades.count_documents({"status": "OPEN"})
    if open_trades >= settings.max_parallel_trades:
        raise HTTPException(status_code=400, detail="Maximum parallel trades reached")
    
    # Check budget
    portfolio = await get_portfolio_summary()
    max_trade_amount = min(
        settings.total_budget_sol * (settings.max_trade_percent / 100),
        settings.max_trade_amount_sol
    )
    
    if trade_data.amount_sol > max_trade_amount:
        raise HTTPException(
            status_code=400, 
            detail=f"Trade amount exceeds max {max_trade_amount:.4f} SOL"
        )
    
    if trade_data.amount_sol > portfolio.available_sol:
        raise HTTPException(status_code=400, detail="Insufficient available balance")
    
    # Additional safety checks for live trading
    if not trade_data.paper_trade:
        # Check daily loss limit
        if abs(portfolio.daily_pnl) >= settings.max_daily_loss_sol:
            raise HTTPException(
                status_code=400, 
                detail=f"Daily loss limit reached ({settings.max_daily_loss_sol} SOL). Live trading paused."
            )
        
        # Check loss streak
        if portfolio.loss_streak >= settings.max_loss_streak:
            raise HTTPException(
                status_code=400,
                detail=f"Loss streak limit reached ({settings.max_loss_streak}). Consider reviewing your strategy."
            )
        
        # Log live trade warning
        logger.warning(f"🔴 LIVE TRADE: {trade_data.token_symbol} - {trade_data.amount_sol} SOL")
    
    # Calculate prices
    take_profit_price = trade_data.price_entry * (1 + trade_data.take_profit_percent / 100)
    stop_loss_price = trade_data.price_entry * (1 - trade_data.stop_loss_percent / 100)
    trailing_stop = None
    if trade_data.trailing_stop_percent:
        trailing_stop = trade_data.price_entry * (1 - trade_data.trailing_stop_percent / 100)
    
    trade = Trade(
        token_address=trade_data.token_address,
        token_symbol=trade_data.token_symbol,
        token_name=trade_data.token_name,
        pair_address=trade_data.pair_address,
        trade_type=trade_data.trade_type,
        amount_sol=trade_data.amount_sol,
        price_entry=trade_data.price_entry,
        price_current=trade_data.price_entry,
        price_peak=trade_data.price_entry,
        take_profit=take_profit_price,
        stop_loss=stop_loss_price,
        trailing_stop=trailing_stop,
        status="OPEN",
        paper_trade=trade_data.paper_trade,
        auto_trade=trade_data.auto_trade,
        wallet_address=trade_data.wallet_address,
        tx_signature=trade_data.tx_signature
    )
    
    doc = trade.model_dump()
    doc["opened_at"] = doc["opened_at"].isoformat()
    await db.trades.insert_one(doc)
    
    trade_type_str = "Paper" if trade_data.paper_trade else "LIVE"
    logger.info(f"[{trade_type_str}] Trade created: {trade.id} - {trade.token_symbol} - {trade.amount_sol} SOL")
    return trade

@api_router.get("/trades", response_model=List[Trade])
async def get_trades(status: Optional[str] = None, limit: int = 100):
    """Get all trades, optionally filtered by status"""
    query = {}
    if status:
        query["status"] = status
    
    trades = await db.trades.find(query, {"_id": 0}).sort("opened_at", -1).to_list(limit)
    
    for trade in trades:
        if isinstance(trade.get("opened_at"), str):
            trade["opened_at"] = datetime.fromisoformat(trade["opened_at"])
        if isinstance(trade.get("closed_at"), str):
            trade["closed_at"] = datetime.fromisoformat(trade["closed_at"])
    
    return [Trade(**t) for t in trades]

@api_router.put("/trades/{trade_id}/close")
async def close_trade(trade_id: str, exit_price: float, reason: str = "MANUAL"):
    """Close a trade with specified exit price"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade["status"] != "OPEN":
        raise HTTPException(status_code=400, detail="Trade is not open")
    
    # Calculate PnL
    pnl_percent = ((exit_price / trade["price_entry"]) - 1) * 100
    pnl_sol = trade["amount_sol"] * (pnl_percent / 100)
    
    update_data = {
        "status": "CLOSED",
        "price_exit": exit_price,
        "price_current": exit_price,
        "pnl": round(pnl_sol, 6),
        "pnl_percent": round(pnl_percent, 2),
        "close_reason": reason,
        "closed_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trades.update_one({"id": trade_id}, {"$set": update_data})
    
    logger.info(f"Trade closed: {trade_id} - PnL: {pnl_percent:.2f}% ({pnl_sol:.6f} SOL)")
    return {"success": True, "pnl": pnl_sol, "pnl_percent": pnl_percent}


@api_router.post("/trades/{trade_id}/close")
async def close_trade_auto(trade_id: str, reason: str = "MANUAL"):
    """
    Close a trade - automatically fetches current price.
    Works for both Paper Mode and Live Mode.
    
    Paper Mode: Simulates trade closing with current price
    Live Mode: Would execute Jupiter swap (not implemented yet)
    """
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade["status"] != "OPEN":
        raise HTTPException(status_code=400, detail="Trade is not open")
    
    # Get current price - use stored price_current or fetch from DEX Screener
    exit_price = trade.get("price_current", trade.get("price_entry", 0))
    
    # Try to fetch live price if we have token address
    token_address = trade.get("token_address")
    pair_address = trade.get("pair_address")
    
    if token_address or pair_address:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client_http:
                # Try to get current price from DEX Screener
                search_addr = pair_address or token_address
                response = await client_http.get(
                    f"https://api.dexscreener.com/latest/dex/tokens/{search_addr}"
                )
                if response.status_code == 200:
                    data = response.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        live_price = float(pairs[0].get("priceUsd", 0) or 0)
                        if live_price > 0:
                            exit_price = live_price
                            logger.info(f"📊 Fetched live price for {trade.get('token_symbol')}: ${exit_price}")
        except Exception as e:
            logger.warning(f"Could not fetch live price, using stored price: {e}")
    
    # Ensure we have a valid exit price
    if exit_price <= 0:
        exit_price = trade.get("price_entry", 0.000001)
        logger.warning(f"Using entry price as exit price for {trade_id}")
    
    # Check if this is paper mode
    is_paper = trade.get("paper_trade", True)
    
    if is_paper:
        # Paper Mode: Simulate trade closing
        logger.info(f"📝 Paper Mode: Closing trade {trade_id} at price ${exit_price}")
    else:
        # Live Mode: Would execute Jupiter swap here
        # For now, we just close locally (swap execution can be added later)
        logger.info(f"💰 Live Mode: Closing trade {trade_id} at price ${exit_price}")
        
        # Validate Jupiter route exists (optional check)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client_http:
                # Check if swap route exists (token -> SOL)
                response = await client_http.get(
                    "https://quote-api.jup.ag/v6/quote",
                    params={
                        "inputMint": token_address,
                        "outputMint": "So11111111111111111111111111111111111111112",
                        "amount": str(int(trade.get("amount_tokens", 1000000))),
                        "slippageBps": 100
                    }
                )
                if response.status_code != 200:
                    logger.warning(f"Jupiter route check failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"Jupiter route validation skipped: {e}")
    
    # Calculate PnL
    entry_price = trade.get("price_entry", exit_price)
    if entry_price > 0:
        pnl_percent = ((exit_price / entry_price) - 1) * 100
    else:
        pnl_percent = 0
    
    pnl_sol = trade.get("amount_sol", 0) * (pnl_percent / 100)
    
    # Update trade in database
    update_data = {
        "status": "CLOSED",
        "price_exit": exit_price,
        "price_current": exit_price,
        "pnl": round(pnl_sol, 6),
        "pnl_percent": round(pnl_percent, 2),
        "close_reason": reason,
        "closed_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trades.update_one({"id": trade_id}, {"$set": update_data})
    
    mode_str = "Paper" if is_paper else "Live"
    logger.info(f"✅ [{mode_str}] Trade closed: {trade.get('token_symbol', trade_id)} - PnL: {pnl_percent:.2f}% ({pnl_sol:.6f} SOL)")
    
    return {
        "success": True, 
        "pnl": round(pnl_sol, 6), 
        "pnl_percent": round(pnl_percent, 2),
        "exit_price": exit_price,
        "mode": mode_str.lower()
    }

@api_router.put("/trades/{trade_id}/update-price")
async def update_trade_price(trade_id: str, current_price: float):
    """Update current price and check TP/SL"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade or trade["status"] != "OPEN":
        raise HTTPException(status_code=404, detail="Open trade not found")
    
    settings = await get_bot_settings()
    update_data = {"price_current": current_price}
    should_close = False
    close_reason = None
    
    # Update peak price for trailing stop
    if current_price > trade.get("price_peak", trade["price_entry"]):
        update_data["price_peak"] = current_price
        
        # Update trailing stop
        if settings.trailing_stop_enabled and trade.get("trailing_stop"):
            new_trailing = current_price * (1 - settings.trailing_stop_percent / 100)
            if new_trailing > trade["trailing_stop"]:
                update_data["trailing_stop"] = new_trailing
    
    # Check take profit
    if current_price >= trade["take_profit"]:
        should_close = True
        close_reason = "TP_HIT"
    
    # Check stop loss
    elif current_price <= trade["stop_loss"]:
        should_close = True
        close_reason = "SL_HIT"
    
    # Check trailing stop
    elif trade.get("trailing_stop") and current_price <= trade["trailing_stop"]:
        should_close = True
        close_reason = "TRAILING_STOP"
    
    await db.trades.update_one({"id": trade_id}, {"$set": update_data})
    
    if should_close:
        return await close_trade(trade_id, current_price, close_reason)
    
    return {"updated": True, "should_close": False}

# ============== PORTFOLIO ENDPOINTS ==============

@api_router.get("/portfolio", response_model=PortfolioSummary)
async def get_portfolio_summary():
    """Get comprehensive portfolio summary with synced wallet balance"""
    settings = await get_bot_settings()
    trades = await db.trades.find({}, {"_id": 0}).to_list(1000)
    
    open_trades = [t for t in trades if t.get("status") == "OPEN"]
    closed_trades = [t for t in trades if t.get("status") == "CLOSED"]
    
    # Calculate values
    in_trades_sol = sum(t.get("amount_sol", 0) for t in open_trades)
    
    # Get actual wallet balance from state (synced via /wallet/balance endpoint)
    actual_wallet_balance = wallet_state.get("balance_sol", 0.0)
    
    # Calculate available SOL:
    # When wallet is connected, available = wallet_balance - in_trades
    # This allows trading with actual wallet funds, not just configured budget
    if actual_wallet_balance > 0:
        # Available = actual wallet balance - what's already in trades
        # This means the trader can use ALL their wallet funds, not limited by budget
        available_sol = max(0, actual_wallet_balance - in_trades_sol)
        logger.info(f"📊 Portfolio: wallet={actual_wallet_balance:.4f} SOL, in_trades={in_trades_sol:.4f}, available={available_sol:.4f}")
    else:
        # No wallet connected - use budget-based calculation
        available_sol = max(0, settings.total_budget_sol - in_trades_sol)
    
    total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
    
    # Win rate
    winning_trades = [t for t in closed_trades if t.get("pnl", 0) > 0]
    win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0
    
    # Best/worst trades
    pnls = [t.get("pnl", 0) for t in closed_trades]
    best_trade = max(pnls) if pnls else 0
    worst_trade = min(pnls) if pnls else 0
    
    # Calculate daily PnL
    today = datetime.now(timezone.utc).date()
    today_trades = [
        t for t in closed_trades 
        if t.get("closed_at") and 
        (datetime.fromisoformat(t["closed_at"]) if isinstance(t["closed_at"], str) else t["closed_at"]).date() == today
    ]
    daily_pnl = sum(t.get("pnl", 0) for t in today_trades)
    
    # Calculate loss streak (respecting reset marker)
    loss_streak = await calculate_current_loss_streak()
    
    # Check if trading should be paused
    is_paused = False
    pause_reason = None
    
    daily_loss_percent = abs(daily_pnl / settings.total_budget_sol * 100) if daily_pnl < 0 else 0
    if daily_loss_percent >= settings.max_daily_loss_percent:
        is_paused = True
        pause_reason = f"Daily loss limit reached ({daily_loss_percent:.1f}%)"
    elif loss_streak >= settings.max_loss_streak:
        is_paused = True
        pause_reason = f"Loss streak limit reached ({loss_streak} consecutive losses)"
    
    total_pnl_percent = (total_pnl / settings.total_budget_sol * 100) if settings.total_budget_sol > 0 else 0
    
    return PortfolioSummary(
        total_budget_sol=settings.total_budget_sol,
        available_sol=round(available_sol, 4),
        in_trades_sol=round(in_trades_sol, 4),
        wallet_balance_sol=round(actual_wallet_balance, 6),
        total_pnl=round(total_pnl, 6),
        total_pnl_percent=round(total_pnl_percent, 2),
        open_trades=len(open_trades),
        closed_trades=len(closed_trades),
        win_rate=round(win_rate, 1),
        best_trade_pnl=round(best_trade, 6),
        worst_trade_pnl=round(worst_trade, 6),
        daily_pnl=round(daily_pnl, 6),
        loss_streak=loss_streak,
        is_paused=is_paused,
        pause_reason=pause_reason
    )

# ============== SMART WALLET TRACKING ==============

@api_router.get("/smart-wallets", response_model=List[SmartWallet])
async def get_smart_wallets():
    """Get list of tracked smart wallets"""
    wallets = await db.smart_wallets.find({"is_tracking": True}, {"_id": 0}).to_list(100)
    return [SmartWallet(**w) for w in wallets]

@api_router.post("/smart-wallets")
async def add_smart_wallet(address: str):
    """Add a wallet to track"""
    existing = await db.smart_wallets.find_one({"address": address})
    if existing:
        raise HTTPException(status_code=400, detail="Wallet already tracked")
    
    wallet = SmartWallet(address=address)
    doc = wallet.model_dump()
    doc["last_seen"] = doc["last_seen"].isoformat()
    await db.smart_wallets.insert_one(doc)
    return wallet

# ============== MARKET DATA ==============

@api_router.get("/market/sol-price")
async def get_current_sol_price():
    """Get current SOL price"""
    price = await get_sol_price()
    return {"price": price, "currency": "USD"}

@api_router.get("/market/trending")
async def get_trending_tokens():
    """Get trending tokens sorted by momentum"""
    tokens = await scan_tokens(limit=10)
    return [t for t in tokens if t.signal_strength in ["MEDIUM", "STRONG"]]

# ============== HEALTH CHECK ==============

@api_router.get("/")
async def root():
    return {"message": "Pump.fun Trading Bot API", "version": "2.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# ============== RPC CONNECTION MANAGER ==============

# Load Helius API key from environment (optional - use public RPCs as fallback)
HELIUS_API_KEY = os.environ.get('HELIUS_API_KEY', '')
HELIUS_RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY else None

# RPC Configuration with failover
# Priority: 1. Helius (if key provided), 2. Ankr, 3. Solana Public
RPC_ENDPOINTS = []
if HELIUS_RPC_URL and HELIUS_API_KEY:
    RPC_ENDPOINTS.append(HELIUS_RPC_URL)
RPC_ENDPOINTS.extend([
    "https://rpc.ankr.com/solana",
    "https://api.mainnet-beta.solana.com",
    "https://solana-mainnet.rpc.extrnode.com"
])

RPC_CONFIG = {
    "primary": RPC_ENDPOINTS[0],
    "endpoints": RPC_ENDPOINTS,
    "timeout": 10,
    "retry_interval": 5,
    "max_retries": 3
}

# RPC State Manager
rpc_state = {
    "connected": False,
    "current_endpoint": None,
    "current_endpoint_index": 0,
    "latency_ms": None,
    "last_check": None,
    "last_slot": None,
    "consecutive_failures": 0,
    "total_requests": 0,
    "failed_requests": 0
}

# Wallet State Manager - synced with actual wallet balance
wallet_state = {
    "address": None,
    "balance_sol": 0.0,
    "last_update": None
}

class RPCStatus(BaseModel):
    connected: bool
    endpoint: Optional[str] = None
    latency_ms: Optional[float] = None
    last_check: Optional[str] = None
    last_slot: Optional[int] = None
    consecutive_failures: int = 0
    success_rate: float = 100.0

async def test_rpc_endpoint(endpoint: str, timeout: int = 10) -> dict:
    """Test a single RPC endpoint and return status"""
    try:
        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            start_time = datetime.now()
            response = await client.post(
                endpoint,
                json={"jsonrpc": "2.0", "id": 1, "method": "getSlot"},
                headers={"Content-Type": "application/json"}
            )
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return {
                        "success": True,
                        "latency_ms": round(latency, 1),
                        "slot": data["result"],
                        "endpoint": endpoint
                    }
                elif "error" in data:
                    return {"success": False, "error": data["error"].get("message", "RPC error")}
            
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except httpx.TimeoutException:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_working_rpc() -> dict:
    """Find a working RPC endpoint with automatic failover"""
    global rpc_state
    
    # Try endpoints in order, starting from current
    for i in range(len(RPC_CONFIG["endpoints"])):
        idx = (rpc_state["current_endpoint_index"] + i) % len(RPC_CONFIG["endpoints"])
        endpoint = RPC_CONFIG["endpoints"][idx]
        
        result = await test_rpc_endpoint(endpoint, RPC_CONFIG["timeout"])
        rpc_state["total_requests"] += 1
        
        if result["success"]:
            # Update state on success
            rpc_state["connected"] = True
            rpc_state["current_endpoint"] = endpoint
            rpc_state["current_endpoint_index"] = idx
            rpc_state["latency_ms"] = result["latency_ms"]
            rpc_state["last_slot"] = result["slot"]
            rpc_state["last_check"] = datetime.now(timezone.utc).isoformat()
            rpc_state["consecutive_failures"] = 0
            
            logger.info(f"✅ RPC connected: {endpoint[:40]}... ({result['latency_ms']}ms, slot {result['slot']})")
            return result
        else:
            rpc_state["failed_requests"] += 1
            logger.warning(f"⚠️ RPC endpoint {idx+1} failed: {result['error']}")
    
    # All endpoints failed
    rpc_state["connected"] = False
    rpc_state["consecutive_failures"] += 1
    rpc_state["last_check"] = datetime.now(timezone.utc).isoformat()
    
    logger.error("❌ All RPC endpoints failed")
    return {"success": False, "error": "All RPC endpoints unavailable"}

async def make_rpc_call(method: str, params: list = None, retries: int = 3) -> dict:
    """Make an RPC call with automatic retry and failover"""
    global rpc_state
    
    for attempt in range(retries):
        # Ensure we have a working endpoint
        if not rpc_state["connected"] or rpc_state["current_endpoint"] is None:
            await get_working_rpc()
        
        if not rpc_state["connected"]:
            if attempt < retries - 1:
                await asyncio.sleep(RPC_CONFIG["retry_interval"])
                continue
            return {"success": False, "error": "No RPC connection available"}
        
        try:
            async with httpx.AsyncClient(timeout=float(RPC_CONFIG["timeout"])) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method
                }
                if params:
                    payload["params"] = params
                
                start_time = datetime.now()
                response = await client.post(
                    rpc_state["current_endpoint"],
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                latency = (datetime.now() - start_time).total_seconds() * 1000
                
                rpc_state["total_requests"] += 1
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        rpc_state["latency_ms"] = round(latency, 1)
                        rpc_state["consecutive_failures"] = 0
                        return {"success": True, "result": data["result"], "latency_ms": latency}
                    elif "error" in data:
                        raise Exception(data["error"].get("message", "RPC error"))
                
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            rpc_state["failed_requests"] += 1
            rpc_state["consecutive_failures"] += 1
            logger.warning(f"RPC call failed (attempt {attempt+1}/{retries}): {e}")
            
            # Try next endpoint on failure
            if rpc_state["consecutive_failures"] >= 2:
                rpc_state["connected"] = False
                await get_working_rpc()
            
            if attempt < retries - 1:
                await asyncio.sleep(1)
    
    return {"success": False, "error": "RPC call failed after retries"}

# Background task for RPC health monitoring
rpc_monitor_task = None

async def rpc_health_monitor():
    """Background task that checks RPC health every 30 seconds"""
    while True:
        try:
            await get_working_rpc()
        except Exception as e:
            logger.error(f"RPC monitor error: {e}")
        
        await asyncio.sleep(30)

@app.on_event("startup")
async def start_rpc_monitor():
    """Start RPC health monitor on app startup"""
    global rpc_monitor_task
    
    # Initial connection test
    await get_working_rpc()
    
    # Start background monitor
    rpc_monitor_task = asyncio.create_task(rpc_health_monitor())
    logger.info("🔌 RPC Health Monitor started")

@app.on_event("shutdown")
async def stop_rpc_monitor():
    """Stop RPC monitor on shutdown"""
    global rpc_monitor_task
    if rpc_monitor_task:
        rpc_monitor_task.cancel()

# ============== RPC API ENDPOINTS ==============

@api_router.get("/rpc/status", response_model=RPCStatus)
async def get_rpc_status():
    """Get current RPC connection status"""
    success_rate = 100.0
    if rpc_state["total_requests"] > 0:
        success_rate = ((rpc_state["total_requests"] - rpc_state["failed_requests"]) / rpc_state["total_requests"]) * 100
    
    return RPCStatus(
        connected=rpc_state["connected"],
        endpoint=rpc_state["current_endpoint"][:40] + "..." if rpc_state["current_endpoint"] else None,
        latency_ms=rpc_state["latency_ms"],
        last_check=rpc_state["last_check"],
        last_slot=rpc_state["last_slot"],
        consecutive_failures=rpc_state["consecutive_failures"],
        success_rate=round(success_rate, 1)
    )

@api_router.post("/rpc/reconnect")
async def reconnect_rpc():
    """Force RPC reconnection"""
    global rpc_state
    rpc_state["connected"] = False
    rpc_state["current_endpoint"] = None
    
    result = await get_working_rpc()
    
    return {
        "success": result["success"],
        "endpoint": rpc_state["current_endpoint"][:40] + "..." if rpc_state["current_endpoint"] else None,
        "latency_ms": rpc_state["latency_ms"]
    }

@api_router.get("/rpc/test")
async def test_all_endpoints():
    """Test all RPC endpoints and return status"""
    results = []
    for endpoint in RPC_CONFIG["endpoints"]:
        result = await test_rpc_endpoint(endpoint)
        results.append({
            "endpoint": endpoint[:50] + "..." if len(endpoint) > 50 else endpoint,
            "success": result["success"],
            "latency_ms": result.get("latency_ms"),
            "slot": result.get("slot"),
            "error": result.get("error")
        })
    
    return {
        "endpoints": results,
        "primary": RPC_CONFIG["primary"][:50] + "...",
        "working_count": sum(1 for r in results if r["success"])
    }

# ============== WALLET BALANCE ENDPOINT (Backend RPC) ==============

@api_router.get("/wallet/balance")
async def get_wallet_balance(address: str):
    """
    Fetch wallet balance via backend RPC
    All Solana RPC calls go through backend - not frontend
    Updates global wallet_state for trading engine sync
    """
    global wallet_state
    
    if not address:
        return {"success": False, "balance": 0, "error": "No address provided"}
    
    # Check RPC connection
    if not rpc_state["connected"]:
        await get_working_rpc()
    
    if not rpc_state["connected"]:
        return {
            "success": False,
            "balance": 0,
            "error": "Solana network unavailable",
            "rpc_status": "disconnected"
        }
    
    # Make RPC call
    result = await make_rpc_call("getBalance", [address])
    
    if result["success"]:
        lamports = result["result"].get("value", 0)
        sol_balance = lamports / 1e9
        
        # Update global wallet state for trading engine
        wallet_state["address"] = address
        wallet_state["balance_sol"] = sol_balance
        wallet_state["last_update"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"💰 Wallet balance updated: {sol_balance:.6f} SOL for {address[:8]}...")
        
        return {
            "success": True,
            "balance": round(sol_balance, 6),
            "lamports": lamports,
            "endpoint": rpc_state["current_endpoint"][:30] + "...",
            "latency_ms": result.get("latency_ms"),
            "rpc_status": "connected"
        }
    
    return {
        "success": False,
        "balance": 0,
        "error": result.get("error", "Failed to fetch balance"),
        "rpc_status": "error"
    }

@api_router.get("/wallet/tokens")
async def get_wallet_tokens(address: str):
    """Get SPL tokens for a wallet address"""
    if not address:
        return {"success": False, "tokens": [], "error": "No address provided"}
    
    if not rpc_state["connected"]:
        await get_working_rpc()
    
    if not rpc_state["connected"]:
        return {"success": False, "tokens": [], "error": "Solana network unavailable"}
    
    # Get token accounts
    result = await make_rpc_call("getTokenAccountsByOwner", [
        address,
        {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
        {"encoding": "jsonParsed"}
    ])
    
    if result["success"]:
        tokens = []
        for account in result["result"].get("value", []):
            try:
                info = account["account"]["data"]["parsed"]["info"]
                token_amount = info.get("tokenAmount", {})
                if token_amount.get("uiAmount", 0) > 0:
                    tokens.append({
                        "mint": info.get("mint"),
                        "balance": token_amount.get("uiAmount", 0),
                        "decimals": token_amount.get("decimals", 0)
                    })
            except:
                continue
        
        return {"success": True, "tokens": tokens, "count": len(tokens)}
    
    return {"success": False, "tokens": [], "error": result.get("error")}

@api_router.post("/wallet/sync")
async def sync_wallet(address: str):
    """
    Sync wallet address and fetch balance - call this when wallet connects
    This ensures the trading engine has the current wallet balance
    """
    global wallet_state
    
    if not address:
        return {"success": False, "error": "No address provided"}
    
    # Fetch balance (this will update wallet_state)
    balance_result = await get_wallet_balance(address)
    
    if balance_result.get("success"):
        logger.info(f"✅ Wallet synced: {address[:8]}... = {balance_result['balance']} SOL")
        return {
            "success": True,
            "address": address,
            "balance": balance_result["balance"],
            "synced_at": wallet_state.get("last_update"),
            "message": "Wallet balance synced with trading engine"
        }
    
    return {
        "success": False,
        "error": balance_result.get("error", "Failed to sync wallet"),
        "message": "Trading engine will use budget-based calculation"
    }

@api_router.post("/wallet/disconnect")
async def disconnect_wallet():
    """Clear wallet state when wallet disconnects"""
    global wallet_state
    
    old_address = wallet_state.get("address")
    wallet_state = {
        "address": None,
        "balance_sol": 0.0,
        "last_update": None
    }
    
    logger.info(f"🔌 Wallet disconnected: {old_address[:8] if old_address else 'none'}...")
    return {"success": True, "message": "Wallet state cleared"}

@api_router.get("/wallet/state")
async def get_wallet_state():
    """Get current wallet state synced with trading engine"""
    return {
        "address": wallet_state.get("address"),
        "balance_sol": wallet_state.get("balance_sol", 0.0),
        "last_update": wallet_state.get("last_update"),
        "synced": wallet_state.get("address") is not None
    }

# ============== SYSTEM DIAGNOSTICS ==============

class SystemHealthStatus(BaseModel):
    wallet_ok: bool = False
    rpc_ok: bool = False
    scanner_ok: bool = False
    trading_engine_ok: bool = False
    database_ok: bool = False
    overall_ok: bool = False
    details: Dict[str, Any] = {}
    timestamp: str

@api_router.get("/system/health", response_model=SystemHealthStatus)
async def system_health_check():
    """Comprehensive system diagnostics"""
    status = {
        "wallet_ok": False,
        "rpc_ok": False,
        "scanner_ok": False,
        "trading_engine_ok": False,
        "database_ok": False,
        "overall_ok": False,
        "details": {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # 1. Check Database
    try:
        await db.command("ping")
        status["database_ok"] = True
        status["details"]["database"] = "MongoDB connected"
    except Exception as e:
        status["details"]["database"] = f"Error: {str(e)}"
    
    # 2. Check RPC Endpoints
    rpc_working = None
    rpc_latency = None
    for endpoint in RPC_ENDPOINTS:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client_http:
                start_time = datetime.now()
                response = await client_http.post(
                    endpoint,
                    json={"jsonrpc": "2.0", "id": 1, "method": "getSlot"}
                )
                latency = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        status["rpc_ok"] = True
                        rpc_working = endpoint
                        rpc_latency = round(latency, 1)
                        status["details"]["rpc"] = {
                            "endpoint": endpoint[:40] + "...",
                            "latency_ms": rpc_latency,
                            "slot": data.get("result")
                        }
                        break
        except Exception as e:
            continue
    
    if not status["rpc_ok"]:
        status["details"]["rpc"] = "All RPC endpoints failed"
    
    # 3. Check Scanner (DEX Screener API)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            response = await client_http.get(
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "SOL"}
            )
            if response.status_code == 200:
                data = response.json()
                pairs_count = len(data.get("pairs", []))
                status["scanner_ok"] = pairs_count > 0
                status["details"]["scanner"] = {
                    "api": "DEX Screener",
                    "pairs_found": pairs_count,
                    "status": "OK" if pairs_count > 0 else "No pairs"
                }
            else:
                status["details"]["scanner"] = f"API returned {response.status_code}"
    except Exception as e:
        status["details"]["scanner"] = f"Error: {str(e)}"
    
    # 4. Check Trading Engine
    status["trading_engine_ok"] = True  # If we got here, FastAPI is running
    status["details"]["trading_engine"] = {
        "auto_trading_active": auto_trading_state["is_running"],
        "scan_count": auto_trading_state["scan_count"],
        "trades_executed": auto_trading_state["trades_executed"]
    }
    
    # 5. Wallet status is determined client-side, mark as OK for API
    status["wallet_ok"] = True  # Frontend will override based on actual wallet connection
    status["details"]["wallet"] = "Check performed client-side"
    
    # Overall status
    status["overall_ok"] = (
        status["database_ok"] and 
        status["rpc_ok"] and 
        status["scanner_ok"] and 
        status["trading_engine_ok"]
    )
    
    return SystemHealthStatus(**status)

@api_router.post("/trading/reset-loss-streak")
async def reset_loss_streak():
    """
    Reset loss streak counter and unpause trading
    Called when user wants to resume trading after losses
    """
    # Get settings and add reset marker
    settings = await get_bot_settings()
    
    # Store reset timestamp to ignore previous losses
    await db.trading_state.update_one(
        {"type": "loss_streak_reset"},
        {"$set": {
            "type": "loss_streak_reset",
            "reset_at": datetime.now(timezone.utc).isoformat(),
            "previous_streak": await calculate_current_loss_streak()
        }},
        upsert=True
    )
    
    logger.info(f"🔄 Loss streak reset by user")
    
    return {
        "success": True,
        "previous_streak": await calculate_current_loss_streak(),
        "message": "Loss streak reset. Trading can resume.",
        "note": "Consider reviewing your strategy before continuing"
    }

async def calculate_current_loss_streak() -> int:
    """Calculate current loss streak, respecting reset markers"""
    # Check for reset marker
    reset_marker = await db.trading_state.find_one({"type": "loss_streak_reset"})
    reset_time = None
    if reset_marker and reset_marker.get("reset_at"):
        reset_time = datetime.fromisoformat(reset_marker["reset_at"])
    
    # Get closed trades
    trades = await db.trades.find(
        {"status": "CLOSED"},
        {"_id": 0}
    ).sort("closed_at", -1).to_list(100)
    
    loss_streak = 0
    for trade in trades:
        closed_at = trade.get("closed_at")
        if closed_at:
            trade_time = datetime.fromisoformat(closed_at) if isinstance(closed_at, str) else closed_at
            # Skip trades before reset
            if reset_time and trade_time < reset_time:
                break
        
        if trade.get("pnl", 0) < 0:
            loss_streak += 1
        else:
            break
    
    return loss_streak

@api_router.get("/trading/can-enable-live")
async def can_enable_live_trading():
    """
    Check if live trading can be safely enabled
    Returns detailed diagnostics
    """
    health = await system_health_check()
    portfolio = await get_portfolio_summary()
    settings = await get_bot_settings()
    
    blockers = []
    warnings = []
    
    # Check RPC
    if not health.rpc_ok:
        blockers.append("RPC connection failed - cannot execute trades")
    
    # Check Scanner
    if not health.scanner_ok:
        blockers.append("Token scanner not working - cannot find opportunities")
    
    # Check Database
    if not health.database_ok:
        blockers.append("Database connection failed")
    
    # Check Portfolio Status
    if portfolio.is_paused:
        blockers.append(f"Trading paused: {portfolio.pause_reason}")
    
    # Check Loss Streak
    if portfolio.loss_streak >= settings.max_loss_streak:
        warnings.append(f"High loss streak ({portfolio.loss_streak}). Consider resetting.")
    
    # Check Daily Loss
    daily_loss_percent = abs(portfolio.daily_pnl / settings.total_budget_sol * 100) if portfolio.daily_pnl < 0 else 0
    if daily_loss_percent >= settings.max_daily_loss_percent * 0.8:
        warnings.append(f"Approaching daily loss limit ({daily_loss_percent:.1f}%)")
    
    # Check Available Budget - now with wallet balance sync info
    if portfolio.available_sol < settings.min_trade_sol:
        # Add more context about the issue
        if wallet_state.get("balance_sol", 0) > 0:
            blockers.append(f"Insufficient available balance ({portfolio.available_sol:.4f} SOL) - wallet has {wallet_state['balance_sol']:.4f} SOL but budget limit is {settings.total_budget_sol:.4f} SOL")
        else:
            blockers.append(f"Insufficient balance ({portfolio.available_sol:.4f} SOL) - connect wallet to sync balance")
    
    can_enable = len(blockers) == 0
    
    return {
        "can_enable": can_enable,
        "blockers": blockers,
        "warnings": warnings,
        "system_health": {
            "rpc": health.rpc_ok,
            "scanner": health.scanner_ok,
            "database": health.database_ok,
            "trading_engine": health.trading_engine_ok
        },
        "portfolio": {
            "available_sol": portfolio.available_sol,
            "wallet_balance_sol": portfolio.wallet_balance_sol,
            "loss_streak": portfolio.loss_streak,
            "is_paused": portfolio.is_paused
        }
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
