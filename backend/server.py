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

# ============== AUTO TRADING ENGINE ==============

# Auto Trading State
auto_trading_state = {
    "is_running": False,
    "last_scan": None,
    "scan_count": 0,
    "trades_executed": 0,
    "errors": [],
    "current_opportunities": []
}

class AutoTradingStatus(BaseModel):
    is_running: bool
    last_scan: Optional[str] = None
    scan_count: int = 0
    trades_executed: int = 0
    scan_interval_seconds: int = 3
    errors: List[str] = []
    current_opportunities: int = 0

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
    """Execute one cycle of the auto trading engine"""
    global auto_trading_state
    
    if not auto_trading_state["is_running"]:
        return {"executed": False, "reason": "Auto trading not running"}
    
    try:
        settings = await get_bot_settings()
        
        # Check if paper mode or live mode
        is_paper = settings.paper_mode
        
        # Get portfolio status
        portfolio = await get_portfolio_summary()
        
        # Check risk limits
        if portfolio.is_paused:
            return {"executed": False, "reason": portfolio.pause_reason}
        
        # Check max parallel trades
        if portfolio.open_trades >= settings.max_parallel_trades:
            return {"executed": False, "reason": "Max parallel trades reached"}
        
        # Scan tokens with enhanced momentum
        logger.info("🔍 Auto Trading: Scanning tokens...")
        
        # Fetch tokens from multiple sources
        pump_pairs = await fetch_pump_fun_tokens()
        dex_pairs = await fetch_dex_screener_tokens(50)
        
        # Combine and dedupe
        all_pairs = {}
        for pair in pump_pairs + dex_pairs:
            address = pair.get("baseToken", {}).get("address", "")
            liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
            volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
            
            # Apply strict filters: liquidity > $5000, volume > $10000
            if address and address not in all_pairs:
                if liquidity >= settings.min_liquidity_usd and volume_24h >= 10000:
                    all_pairs[address] = pair
        
        # Analyze each token
        opportunities = []
        for address, pair in all_pairs.items():
            try:
                # Calculate enhanced momentum
                (
                    momentum_score, signal_strength, signals, signal_reasons, 
                    buy_signal, buys_5m, sells_5m, volume_5m, price_5m, price_1h
                ) = calculate_enhanced_momentum(pair, settings)
                
                # Check if token passes all filters
                risk_analysis = calculate_risk_analysis(pair, settings)
                
                if not risk_analysis.passed_filters:
                    continue
                
                # Check age constraints
                created_at = pair.get("pairCreatedAt", 0)
                if created_at:
                    age_hours = (datetime.now(timezone.utc).timestamp() * 1000 - created_at) / (1000 * 60 * 60)
                else:
                    age_hours = 999
                
                min_age_hours = settings.min_token_age_minutes / 60
                if age_hours < min_age_hours or age_hours > settings.max_token_age_hours:
                    continue
                
                # Check buy/sell ratio
                buy_sell_ratio = buys_5m / max(sells_5m, 1)
                if buy_sell_ratio < settings.min_buy_sell_ratio:
                    continue
                
                # Only consider strong buy signals
                if buy_signal and momentum_score >= 70:
                    base_token = pair.get("baseToken", {})
                    
                    opportunity = {
                        "address": address,
                        "symbol": base_token.get("symbol", "???"),
                        "name": base_token.get("name", "Unknown"),
                        "price_usd": float(pair.get("priceUsd", 0) or 0),
                        "momentum_score": momentum_score,
                        "signal_strength": signal_strength,
                        "signal_reasons": signal_reasons,
                        "risk_score": risk_analysis.risk_score,
                        "liquidity": float(pair.get("liquidity", {}).get("usd", 0) or 0),
                        "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
                        "pair_address": pair.get("pairAddress"),
                        "buy_sell_ratio": buy_sell_ratio
                    }
                    opportunities.append(opportunity)
                    
            except Exception as e:
                logger.error(f"Error analyzing token {address}: {e}")
                continue
        
        # Sort by momentum score
        opportunities.sort(key=lambda x: x["momentum_score"], reverse=True)
        
        # Update state
        auto_trading_state["last_scan"] = datetime.now(timezone.utc).isoformat()
        auto_trading_state["scan_count"] += 1
        auto_trading_state["current_opportunities"] = opportunities[:5]
        
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

async def auto_trading_loop():
    """Background loop that runs every 3 seconds"""
    global auto_trading_state
    
    while auto_trading_state["is_running"]:
        try:
            result = await execute_auto_trade_cycle()
            if result.get("executed"):
                logger.info(f"✅ Auto trade executed: {result.get('token')} for {result.get('amount')} SOL")
        except Exception as e:
            logger.error(f"Auto trading loop error: {e}")
        
        # Wait 3 seconds before next cycle
        await asyncio.sleep(3)

@api_router.post("/auto-trading/start")
async def start_auto_trading(background_tasks: BackgroundTasks):
    """Start the auto trading engine"""
    global auto_trading_state, auto_trading_task
    
    if auto_trading_state["is_running"]:
        return {"success": False, "message": "Auto trading already running"}
    
    auto_trading_state["is_running"] = True
    auto_trading_state["scan_count"] = 0
    auto_trading_state["trades_executed"] = 0
    auto_trading_state["errors"] = []
    
    # Start background task
    auto_trading_task = asyncio.create_task(auto_trading_loop())
    
    logger.info("🚀 Auto Trading Engine Started (3s interval)")
    return {"success": True, "message": "Auto trading started", "interval": 3}

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
    
    logger.info("🛑 Auto Trading Engine Stopped")
    return {
        "success": True, 
        "message": "Auto trading stopped",
        "stats": {
            "scan_count": auto_trading_state["scan_count"],
            "trades_executed": auto_trading_state["trades_executed"]
        }
    }

@api_router.get("/auto-trading/status", response_model=AutoTradingStatus)
async def get_auto_trading_status():
    """Get current auto trading status"""
    return AutoTradingStatus(
        is_running=auto_trading_state["is_running"],
        last_scan=auto_trading_state["last_scan"],
        scan_count=auto_trading_state["scan_count"],
        trades_executed=auto_trading_state["trades_executed"],
        scan_interval_seconds=3,
        errors=[e.get("error", "") for e in auto_trading_state["errors"][-5:]],
        current_opportunities=len(auto_trading_state.get("current_opportunities", []))
    )

@api_router.get("/auto-trading/opportunities")
async def get_current_opportunities():
    """Get current detected opportunities from auto trading"""
    return auto_trading_state.get("current_opportunities", [])

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
    try:
        async with httpx.AsyncClient(timeout=15.0) as client_http:
            # Get trending pairs
            response = await client_http.get(
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "solana"}
            )
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                # Filter Solana pairs
                solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                return solana_pairs[:limit]
    except Exception as e:
        logger.error(f"Error fetching DEX Screener data: {e}")
    return []

async def fetch_pump_fun_tokens() -> List[Dict]:
    """Fetch new tokens from Pump.fun via DEX Screener"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client_http:
            response = await client_http.get(
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "pump.fun"}
            )
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                return [p for p in pairs if p.get("chainId") == "solana"][:30]
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
    
    # Combine and dedupe
    all_pairs = {}
    for pair in pump_pairs + dex_pairs:
        address = pair.get("baseToken", {}).get("address", "")
        if address and address not in all_pairs:
            all_pairs[address] = pair
    
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
    """Close a trade"""
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
    """Get comprehensive portfolio summary"""
    settings = await get_bot_settings()
    trades = await db.trades.find({}, {"_id": 0}).to_list(1000)
    
    open_trades = [t for t in trades if t.get("status") == "OPEN"]
    closed_trades = [t for t in trades if t.get("status") == "CLOSED"]
    
    # Calculate values
    in_trades_sol = sum(t.get("amount_sol", 0) for t in open_trades)
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
    
    # Calculate loss streak
    loss_streak = 0
    for trade in reversed(closed_trades):
        if trade.get("pnl", 0) < 0:
            loss_streak += 1
        else:
            break
    
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
