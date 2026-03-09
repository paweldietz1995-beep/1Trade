from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import time
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
import base58

# Solana native imports
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.system_program import TransferParams, transfer

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
    # SCALPING CAPITAL MANAGEMENT
    total_budget_sol: float = 3.0
    max_trade_percent: float = 1.0     # Max 1% of budget per trade
    min_trade_sol: float = 0.005       # Min 0.005 SOL per trade
    max_parallel_trades: int = 30      # 20-40 simultaneous trades
    max_trade_amount_sol: float = 0.03 # Max 0.03 SOL per trade
    # SCALPING RISK MANAGEMENT
    take_profit_percent: float = 10.0  # 8-12% take profit
    stop_loss_percent: float = 7.0     # 6-8% stop loss
    trailing_stop_enabled: bool = True
    trailing_stop_percent: float = 4.0
    max_daily_loss_percent: float = 20.0
    max_daily_loss_sol: float = 0.6    # Max daily loss
    max_loss_streak: int = 10          # Max consecutive losses
    # Live Trading Safety
    require_confirmation: bool = True
    first_live_trade_done: bool = False
    slippage_bps: int = 150            # 1.5% slippage for speed
    # MOMENTUM TOKEN FILTERS
    min_liquidity_usd: float = 500.0   # $500 minimum
    min_volume_usd: float = 500.0      # $500 minimum
    max_dev_wallet_percent: float = 25.0
    max_top10_wallet_percent: float = 70.0
    min_token_age_seconds: int = 30    # Min 30 seconds old
    max_token_age_hours: int = 4       # Max 4 hours old
    min_buy_sell_ratio: float = 1.05   # Buy pressure required
    # MOMENTUM THRESHOLDS
    min_momentum_score: int = 25       # Score threshold
    min_volume_surge_percent: float = 5.0
    min_buyers_1m: int = 3             # 3 buyers in 1 minute
    # Automation
    auto_trade_enabled: bool = False
    paper_mode: bool = True
    scan_interval_seconds: float = 1.0 # 1 second scanning
    # Advanced
    smart_wallet_tracking: bool = True
    migration_detection: bool = True
    sniper_mode: bool = True
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
# ============== HIGH-FREQUENCY MOMENTUM SCALPING CONFIGURATION ==============
ENGINE_CONFIG = {
    # HIGH-FREQUENCY SCANNING (0.8-1.2s interval)
    "scan_interval_seconds": 1.0,      # 1 second scans
    "max_tokens_per_scan": 1000,       # Process up to 1000 tokens
    "max_signals_per_scan": 500,       # Analyze top 500 signals
    "max_open_trades": 30,             # 20-40 simultaneous trades (realistic)
    "max_trades_per_token": 1,         # Only 1 trade per token
    "signal_cooldown_seconds": 60,     # 60 second cooldown per token
    "min_signal_score": 25,            # Minimum score for opportunities
    
    # SCALPING PROFIT TARGETS (quick exits)
    "take_profit_percent": 10,         # 8-12% take profit
    "stop_loss_percent": 7,            # 6-8% stop loss
    "trailing_stop_enabled": True,
    "trailing_stop_percent": 4,        # 4% trailing stop
    "trailing_stop_activation": 5,     # Activate after 5% profit
    "daily_loss_limit_percent": 20,    # 20% max daily loss
    "loss_streak_limit": 10,           # 10 consecutive losses max
    
    # MOMENTUM FILTERS (aggressive but safe)
    "min_liquidity_usd": 500,          # $500 minimum liquidity
    "min_volume_usd": 500,             # $500 minimum volume
    "min_volume_5m": 500,              # $500 5-minute volume
    "min_volume_surge_percent": 5,     # 5% volume surge
    "min_buy_sell_ratio": 1.05,        # Buy pressure required
    "min_buyers_1m": 3,                # 3 buyers in 1 minute
    "min_momentum_score": 25,          # Momentum threshold
    "min_price_change_1m": 2,          # 2% price change in 1m (momentum signal)
    "max_token_age_hours": 4,          # Tokens < 4 hours old
    "min_token_age_seconds": 30,       # At least 30 seconds old
    "price_update_interval": 1,        # Update prices every 1 second
    
    # MOMENTUM ENTRY SIGNAL (1-minute based)
    "momentum_volume_multiplier": 1.5, # 1.5x baseline volume required
    "momentum_price_change_min": 2,    # 2% price change for momentum
    
    # NEW TOKEN PRIORITY BONUS
    "new_token_age_seconds": 120,      # Tokens < 2 minutes old get bonus
    "new_token_priority_bonus": 30,    # +30 priority score for new tokens
    "ultra_new_token_seconds": 60,     # Tokens < 1 minute old
    "ultra_new_token_bonus": 50,       # +50 priority for ultra-new
    
    # EARLY PUMP DETECTION
    "early_pump_volume_surge": 100,    # 100% volume surge for early pump
    "early_pump_price_change_1m": 2,   # 2% price change in 1 minute
    "early_pump_min_liquidity": 1000,  # $1k min liquidity for early pumps
    
    # MICRO-TRADE POSITION SIZING (0.5%-1% of wallet)
    "micro_trade_percent": 0.75,       # 0.75% of wallet per trade
    "max_micro_trade_sol": 0.03,       # Max 0.03 SOL per micro-trade
    "min_micro_trade_sol": 0.005,      # Min 0.005 SOL per micro-trade
    
    # Smart Wallet Tracking
    "smart_wallet_min_profit": 25,     # 25% min profit to track wallet
    "smart_wallet_min_trades": 3,      # 3 min trades to qualify
    "copy_trade_delay_ms": 100,        # 100ms delay for copy trades
    
    # Risk Management
    "max_daily_trades": 300,           # Max trades per day
    "max_portfolio_risk": 0.35,        # 35% max portfolio at risk
    
    # SCANNER SOURCES (all parallel)
    "scanner_sources": [
        "dexscreener",
        "birdeye", 
        "jupiter",
        "raydium",
        "orca",
        "meteora",
        "pumpfun"
    ],
}


# ============== API FAILOVER SYSTEM ==============
class APIFailover:
    """Manages API failover for data sources"""
    
    def __init__(self):
        self.primary_api = "dexscreener"
        self.fallback_apis = ["birdeye", "jupiter"]
        self.api_status = {
            "dexscreener": {"healthy": True, "last_check": None, "failures": 0},
            "birdeye": {"healthy": True, "last_check": None, "failures": 0},
            "jupiter": {"healthy": True, "last_check": None, "failures": 0}
        }
        self.max_failures = 3
        
    def mark_failure(self, api_name: str):
        """Mark an API as failed"""
        if api_name in self.api_status:
            self.api_status[api_name]["failures"] += 1
            if self.api_status[api_name]["failures"] >= self.max_failures:
                self.api_status[api_name]["healthy"] = False
                logger.warning(f"⚠️ API {api_name} marked as unhealthy after {self.max_failures} failures")
    
    def mark_success(self, api_name: str):
        """Mark an API call as successful"""
        if api_name in self.api_status:
            self.api_status[api_name]["failures"] = 0
            self.api_status[api_name]["healthy"] = True
            self.api_status[api_name]["last_check"] = datetime.now(timezone.utc)
    
    def get_healthy_api(self) -> str:
        """Get the best healthy API"""
        if self.api_status[self.primary_api]["healthy"]:
            return self.primary_api
        for api in self.fallback_apis:
            if self.api_status[api]["healthy"]:
                return api
        # Reset all if none healthy
        for api in self.api_status:
            self.api_status[api]["healthy"] = True
            self.api_status[api]["failures"] = 0
        return self.primary_api
    
    def get_status(self) -> dict:
        return self.api_status

api_failover = APIFailover()


# ============== EARLY PUMP DETECTOR ==============
class EarlyPumpDetector:
    """Detects early pump signals for tokens"""
    
    def __init__(self):
        self.detected_pumps = {}  # token_address -> detection_time
        self.pump_cooldown = 300  # 5 minutes cooldown per token
    
    def check_early_pump(self, pair: dict) -> tuple:
        """
        Check if token shows early pump signals.
        Returns: (is_pump, confidence, reasons)
        
        Early Pump Conditions:
        - Liquidity > $10k
        - Volume 5m increase > 300%
        - Buys > Sells
        - Price change 1m > 3%
        """
        reasons = []
        confidence = 0
        
        # Get metrics
        liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        volume_5m = float(pair.get("volume", {}).get("m5", 0) or 0)
        volume_1h = float(pair.get("volume", {}).get("h1", 0) or 0)
        price_change_1m = float(pair.get("priceChange", {}).get("m5", 0) or 0) / 5  # Approximate 1m
        price_change_5m = float(pair.get("priceChange", {}).get("m5", 0) or 0)
        
        txns_5m = pair.get("txns", {}).get("m5", {})
        buys_5m = txns_5m.get("buys", 0)
        sells_5m = txns_5m.get("sells", 0)
        
        token_address = pair.get("baseToken", {}).get("address", "")
        
        # Check cooldown
        if token_address in self.detected_pumps:
            time_since = (datetime.now(timezone.utc) - self.detected_pumps[token_address]).total_seconds()
            if time_since < self.pump_cooldown:
                return (False, 0, ["In cooldown"])
        
        # CHECK 1: Liquidity threshold
        min_liq = ENGINE_CONFIG.get("early_pump_min_liquidity", 10000)
        if liquidity >= min_liq:
            confidence += 20
            reasons.append(f"Liquidity ${liquidity:.0f} >= ${min_liq}")
        else:
            return (False, 0, [f"Low liquidity: ${liquidity:.0f}"])
        
        # CHECK 2: Volume surge
        avg_volume_1h = volume_1h / 12 if volume_1h > 0 else 0  # 5min avg
        volume_surge_percent = ENGINE_CONFIG.get("early_pump_volume_surge", 300)
        if avg_volume_1h > 0:
            surge = (volume_5m / avg_volume_1h) * 100
            if surge >= volume_surge_percent:
                confidence += 30
                reasons.append(f"Volume surge {surge:.0f}%")
        
        # CHECK 3: Buy pressure
        if buys_5m > sells_5m and buys_5m > 5:
            buy_ratio = buys_5m / max(sells_5m, 1)
            if buy_ratio >= 1.5:
                confidence += 25
                reasons.append(f"Strong buy pressure: {buy_ratio:.1f}x")
        
        # CHECK 4: Price momentum
        price_threshold = ENGINE_CONFIG.get("early_pump_price_change_1m", 3)
        if price_change_5m >= price_threshold * 2:  # 5m threshold is 2x 1m
            confidence += 25
            reasons.append(f"Price momentum +{price_change_5m:.1f}%")
        
        is_pump = confidence >= 60
        
        if is_pump:
            self.detected_pumps[token_address] = datetime.now(timezone.utc)
            logger.info(f"🚀 EARLY PUMP DETECTED: {pair.get('baseToken', {}).get('symbol')} - Confidence: {confidence}%")
        
        return (is_pump, confidence, reasons)

early_pump_detector = EarlyPumpDetector()


# ============== SMART WALLET TRACKER ==============
class SmartWalletTracker:
    """Tracks profitable wallets and generates copy trade signals"""
    
    def __init__(self):
        self.tracked_wallets = {}  # address -> wallet_data
        self.wallet_trades = {}    # address -> [trades]
        self.copy_signals = []     # Pending copy trade signals
        
    async def load_wallets_from_db(self):
        """Load tracked wallets from database"""
        try:
            wallets = await db.smart_wallets.find({"is_tracking": True}, {"_id": 0}).to_list(100)
            for w in wallets:
                self.tracked_wallets[w["address"]] = w
            logger.info(f"👛 Loaded {len(wallets)} smart wallets from database")
        except Exception as e:
            logger.error(f"Error loading smart wallets: {e}")
    
    def add_wallet(self, address: str, name: str = None, profit_rate: float = 0):
        """Add a wallet to track"""
        self.tracked_wallets[address] = {
            "address": address,
            "name": name or f"Wallet_{address[:8]}",
            "profit_rate": profit_rate,
            "trades_count": 0,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "is_tracking": True
        }
    
    def record_wallet_trade(self, wallet_address: str, token_address: str, trade_type: str, price: float):
        """Record a trade from a tracked wallet"""
        if wallet_address not in self.wallet_trades:
            self.wallet_trades[wallet_address] = []
        
        trade = {
            "token_address": token_address,
            "trade_type": trade_type,  # BUY or SELL
            "price": price,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.wallet_trades[wallet_address].append(trade)
        
        # Generate copy signal for BUY trades
        if trade_type == "BUY":
            self.copy_signals.append({
                "wallet": wallet_address,
                "token": token_address,
                "price": price,
                "created_at": datetime.now(timezone.utc),
                "executed": False
            })
            logger.info(f"📋 Copy trade signal from {wallet_address[:8]}... for token {token_address[:8]}...")
    
    def get_pending_copy_signals(self) -> list:
        """Get pending copy trade signals"""
        pending = [s for s in self.copy_signals if not s["executed"]]
        return pending[:5]  # Max 5 at a time
    
    def mark_signal_executed(self, signal_index: int):
        """Mark a copy signal as executed"""
        if 0 <= signal_index < len(self.copy_signals):
            self.copy_signals[signal_index]["executed"] = True
    
    def get_wallet_stats(self, address: str) -> dict:
        """Get statistics for a tracked wallet"""
        trades = self.wallet_trades.get(address, [])
        return {
            "address": address,
            "total_trades": len(trades),
            "buys": sum(1 for t in trades if t["trade_type"] == "BUY"),
            "sells": sum(1 for t in trades if t["trade_type"] == "SELL")
        }

smart_wallet_tracker = SmartWalletTracker()


# ============== CRASH RECOVERY SYSTEM ==============
class CrashRecovery:
    """Handles crash recovery and state persistence"""
    
    def __init__(self):
        self.state_file = "/tmp/trading_bot_state.json"
        
    async def save_state(self):
        """Save current trading state to database"""
        try:
            state = {
                "is_running": auto_trading_state["is_running"],
                "scan_count": auto_trading_state["scan_count"],
                "trades_executed": auto_trading_state["trades_executed"],
                "trades_today": auto_trading_state["trades_today"],
                "daily_pnl": auto_trading_state["daily_pnl"],
                "saved_at": datetime.now(timezone.utc).isoformat()
            }
            await db.bot_state.update_one(
                {"type": "trading_state"},
                {"$set": state},
                upsert=True
            )
            logger.debug("💾 Bot state saved to database")
        except Exception as e:
            logger.error(f"Error saving bot state: {e}")
    
    async def load_state(self) -> dict:
        """Load trading state from database"""
        try:
            state = await db.bot_state.find_one({"type": "trading_state"}, {"_id": 0})
            if state:
                logger.info(f"📥 Loaded bot state from database (saved at {state.get('saved_at')})")
                return state
        except Exception as e:
            logger.error(f"Error loading bot state: {e}")
        return None
    
    async def recover_active_trades(self):
        """Recover active trades after crash"""
        try:
            active_trades = await db.trades.find({"status": "OPEN"}, {"_id": 0}).to_list(100)
            if active_trades:
                logger.info(f"🔄 Recovered {len(active_trades)} active trades from database")
                # Log recovery event
                activity_feed.add_event("INFO", "SYSTEM", {
                    "message": f"Recovered {len(active_trades)} active trades after restart"
                })
            return active_trades
        except Exception as e:
            logger.error(f"Error recovering trades: {e}")
            return []
    
    async def check_and_recover(self):
        """Check for crashed state and recover if needed"""
        state = await self.load_state()
        if state and state.get("is_running"):
            logger.warning("⚠️ Detected previous running state - recovering...")
            await self.recover_active_trades()
            return True
        return False

crash_recovery = CrashRecovery()

# Activity Feed - stores recent trading events
class ActivityFeed:
    def __init__(self, max_events: int = 100):
        self.events = []
        self.max_events = max_events
    
    def add_event(self, event_type: str, token: str, data: dict = None):
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,  # BUY, SELL, SIGNAL, SCAN, TP_HIT, SL_HIT, ERROR, INFO
            "token": token,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.events.insert(0, event)
        if len(self.events) > self.max_events:
            self.events = self.events[:self.max_events]
        return event
    
    def get_events(self, limit: int = 50) -> list:
        return self.events[:limit]
    
    def log_bot_scan(self, tokens_found: int, opportunities: int):
        """Log scanner activity"""
        self.add_event("SCAN", "SCANNER", {
            "tokens_found": tokens_found,
            "opportunities": opportunities,
            "message": f"Scanned {tokens_found} tokens, found {opportunities} opportunities"
        })
    
    def log_bot_buy(self, token: str, price: float, amount_sol: float, signal_score: int, reasons: list = None):
        """Log buy execution"""
        self.add_event("BUY", token, {
            "price": price,
            "amount_sol": amount_sol,
            "signal_score": signal_score,
            "reasons": reasons or [],
            "message": f"BUY {token} @ ${price:.8f} | {amount_sol:.4f} SOL | Score: {signal_score}"
        })
    
    def log_bot_sell(self, token: str, entry_price: float, exit_price: float, pnl_sol: float, pnl_percent: float, reason: str):
        """Log sell execution"""
        pnl_str = f"+{pnl_sol:.6f}" if pnl_sol >= 0 else f"{pnl_sol:.6f}"
        roi_str = f"+{pnl_percent:.2f}" if pnl_percent >= 0 else f"{pnl_percent:.2f}"
        self.add_event("SELL", token, {
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl_sol": pnl_sol,
            "pnl_percent": pnl_percent,
            "reason": reason,
            "message": f"SELL {token} @ ${exit_price:.8f} | P&L: {pnl_str} SOL ({roi_str}%) | {reason}"
        })
    
    def log_tp_hit(self, token: str, roi: float):
        """Log take profit trigger"""
        self.add_event("TP_HIT", token, {
            "roi": roi,
            "message": f"🎯 TAKE PROFIT HIT {token} at +{roi:.2f}%"
        })
    
    def log_sl_hit(self, token: str, roi: float):
        """Log stop loss trigger"""
        self.add_event("SL_HIT", token, {
            "roi": roi,
            "message": f"⚠️ STOP LOSS HIT {token} at {roi:.2f}%"
        })
    
    def log_signal(self, token: str, signal_type: str, strength: str, score: int):
        """Log signal detection"""
        self.add_event("SIGNAL", token, {
            "signal_type": signal_type,
            "strength": strength,
            "score": score,
            "message": f"📊 {strength} signal detected: {token} (Score: {score})"
        })
    
    def log_anti_rug(self, token: str, risk_level: str, reasons: list):
        """Log anti-rug check"""
        self.add_event("ANTI_RUG", token, {
            "risk_level": risk_level,
            "reasons": reasons,
            "message": f"🛡️ Anti-rug check {token}: {risk_level} risk"
        })

activity_feed = ActivityFeed(max_events=100)

# Token Cache to reduce API calls
class TokenCache:
    def __init__(self, ttl_seconds: int = 30):
        self.tokens = []
        self.last_updated = None
        self.ttl_seconds = ttl_seconds
    
    def is_valid(self) -> bool:
        if not self.last_updated:
            return False
        age = (datetime.now(timezone.utc) - self.last_updated).total_seconds()
        return age < self.ttl_seconds
    
    def set(self, tokens: list):
        self.tokens = tokens
        self.last_updated = datetime.now(timezone.utc)
    
    def get(self) -> list:
        return self.tokens if self.is_valid() else []

token_cache = TokenCache(ttl_seconds=15)  # Cache tokens for 15 seconds

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
    # RELAXED: Check buyers >= 5 in last 5 minutes and buy/sell ratio >= 1.0
    buy_sell_ratio_5m = buys_5m / max(sells_5m, 1)
    buy_pressure_triggered = buys_5m >= 5 and buy_sell_ratio_5m >= 1.0
    
    strength = "STRONG" if buys_5m >= 30 and buy_sell_ratio_5m >= 2.0 else \
               "MEDIUM" if buys_5m >= 15 and buy_sell_ratio_5m >= 1.5 else \
               "WEAK" if buys_5m >= 5 and buy_sell_ratio_5m >= 1.0 else "NONE"
    
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
    base_score = 50  # Higher base score for more opportunities
    
    # Volume surge bonus
    if volume_surge_triggered:
        base_score += 20 if signals[0].strength == "STRONG" else 15 if signals[0].strength == "MEDIUM" else 8
    elif volume_5m > 500:  # Partial bonus for any decent volume
        base_score += 5
    
    # Buy pressure bonus - RELAXED THRESHOLDS
    if buy_pressure_triggered:
        base_score += 25 if signals[1].strength == "STRONG" else 18 if signals[1].strength == "MEDIUM" else 10
    elif buys_5m >= 10 and buy_sell_ratio_5m >= 1.0:  # Partial bonus
        base_score += 8
    elif buys_5m >= 5:  # Any buying activity
        base_score += 4
    
    # Wallet growth bonus
    if wallet_growth_triggered:
        base_score += 15 if signals[2].strength == "STRONG" else 10 if signals[2].strength == "MEDIUM" else 5
    
    # Price acceleration bonus
    if price_acceleration_triggered:
        base_score += 15 if signals[3].strength == "STRONG" else 10 if signals[3].strength == "MEDIUM" else 5
    elif price_change_5m > 2:  # Any positive momentum
        base_score += 5
    
    # Liquidity bonus/penalty - RELAXED
    if liquidity >= 20000:
        base_score += 8
    elif liquidity >= 5000:
        base_score += 4
    elif liquidity < 1000:
        base_score -= 5  # Reduced penalty
    
    combined_score = min(100, max(0, base_score))
    
    # Determine signal strength - LOWERED THRESHOLDS
    if combined_score >= 70:
        signal_strength = "STRONG"
    elif combined_score >= 55:
        signal_strength = "MEDIUM"
    elif combined_score >= 40:
        signal_strength = "WEAK"
    else:
        signal_strength = "NONE"
    
    # Build signal reasons
    signal_reasons = []
    for sig in signals:
        if sig.triggered:
            signal_reasons.append(sig.description)
    
    # Determine if this is a BUY signal - MUCH MORE PERMISSIVE
    # Any triggered signal OR decent score is enough
    any_signal_triggered = any(s.triggered for s in signals)
    strong_signals = sum(1 for s in signals if s.triggered and s.strength in ["STRONG", "MEDIUM"])
    
    # Buy signal if: 1+ strong/medium signal, OR score >= 50, OR any signal with score >= 40
    buy_signal = (
        strong_signals >= 1 or 
        combined_score >= 50 or 
        (any_signal_triggered and combined_score >= 40)
    )
    
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


async def check_anti_rug_filters(pair: Dict) -> tuple:
    """
    Anti-rug pull filter checks:
    - Liquidity requirements
    - Top holder concentration
    - Token age
    - Transaction activity
    
    Returns: (is_safe, risk_level, reasons)
    """
    reasons = []
    risk_score = 0
    
    # Get token data
    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
    txns_24h = pair.get("txns", {}).get("h24", {})
    buys_24h = txns_24h.get("buys", 0)
    sells_24h = txns_24h.get("sells", 0)
    
    # Get pair age in hours
    pair_created = pair.get("pairCreatedAt", 0)
    if pair_created:
        age_hours = (datetime.now(timezone.utc).timestamp() * 1000 - pair_created) / (1000 * 60 * 60)
    else:
        age_hours = 999  # Unknown age, assume old
    
    # ===== CHECK 1: LIQUIDITY =====
    # Minimum $20k liquidity required
    min_liquidity = ENGINE_CONFIG.get("min_liquidity_usd", 2000)
    if liquidity < min_liquidity:
        risk_score += 30
        reasons.append(f"Low liquidity: ${liquidity:.0f} < ${min_liquidity}")
    elif liquidity < 10000:
        risk_score += 15
        reasons.append(f"Medium liquidity: ${liquidity:.0f}")
    
    # ===== CHECK 2: VOLUME TO LIQUIDITY RATIO =====
    # Suspicious if volume >> liquidity (potential wash trading)
    if liquidity > 0:
        vol_liq_ratio = volume_24h / liquidity
        if vol_liq_ratio > 100:
            risk_score += 25
            reasons.append(f"Suspicious volume ratio: {vol_liq_ratio:.0f}x liquidity")
        elif vol_liq_ratio > 50:
            risk_score += 10
            reasons.append(f"High volume ratio: {vol_liq_ratio:.0f}x liquidity")
    
    # ===== CHECK 3: TOKEN AGE =====
    # Very new tokens are riskier
    if age_hours < 1:
        risk_score += 20
        reasons.append(f"Very new token: {age_hours:.1f} hours old")
    elif age_hours < 6:
        risk_score += 10
        reasons.append(f"New token: {age_hours:.1f} hours old")
    
    # ===== CHECK 4: TRANSACTION ACTIVITY =====
    # Low transaction count is suspicious
    total_txns = buys_24h + sells_24h
    if total_txns < 50:
        risk_score += 15
        reasons.append(f"Low activity: {total_txns} transactions in 24h")
    
    # ===== CHECK 5: BUY/SELL BALANCE =====
    # Extreme imbalance might indicate manipulation
    if buys_24h > 0 and sells_24h > 0:
        ratio = max(buys_24h, sells_24h) / min(buys_24h, sells_24h)
        if ratio > 10:
            risk_score += 15
            reasons.append(f"Imbalanced trades: {ratio:.0f}x ratio")
    
    # Determine risk level
    if risk_score >= 50:
        risk_level = "HIGH"
        is_safe = False
    elif risk_score >= 30:
        risk_level = "MEDIUM"
        is_safe = True  # Allow with caution
    else:
        risk_level = "LOW"
        is_safe = True
    
    # Log anti-rug check
    token_symbol = pair.get("baseToken", {}).get("symbol", "???")
    logger.debug(f"🛡️ Anti-rug check {token_symbol}: {risk_level} (score: {risk_score})")
    
    return (is_safe, risk_level, risk_score, reasons)

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
        
        # Calculate available slots for multi-trade
        available_slots = max_trades - portfolio.open_trades
        if available_slots <= 0:
            return {"executed": False, "reason": f"Max parallel trades reached ({max_trades})"}
        
        # Get existing open trade tokens to avoid duplicates
        existing_open_trades = await db.trades.find(
            {"status": "OPEN"}, 
            {"token_address": 1, "_id": 0}
        ).to_list(100)
        active_trade_tokens = set(t.get("token_address") for t in existing_open_trades)
        
        logger.info(f"📈 MULTI-TRADE MODE: {available_slots} slots available (max: {max_trades}, open: {portfolio.open_trades})")
        
        # Execute multiple trades
        trades_executed = []
        
        for opp in opportunities:
            # Check if we've filled all available slots
            if len(trades_executed) >= available_slots:
                logger.info(f"🛑 Max trades reached ({len(trades_executed)}/{available_slots})")
                break
            
            # Skip if already trading this token
            if opp["address"] in active_trade_tokens:
                continue
            
            # Check minimum confidence
            if opp["momentum_score"] < 70:
                continue
            
            # Calculate trade amount
            trade_amount = min(
                settings.total_budget_sol * (settings.max_trade_percent / 100),
                settings.max_trade_amount_sol,
                portfolio.available_sol / max(1, available_slots - len(trades_executed))  # Divide remaining budget
            )
            
            if trade_amount < settings.min_trade_sol:
                continue
            
            # Execute trade
            try:
                trade_data = TradeCreate(
                    token_address=opp["address"],
                    token_symbol=opp["symbol"],
                    token_name=opp["name"],
                    pair_address=opp.get("pair_address"),
                    trade_type="BUY",
                    amount_sol=trade_amount,
                    price_entry=opp["price_usd"],
                    take_profit_percent=settings.take_profit_percent,
                    stop_loss_percent=settings.stop_loss_percent,
                    trailing_stop_percent=settings.trailing_stop_percent if settings.trailing_stop_enabled else None,
                    paper_trade=is_paper,
                    auto_trade=True
                )
                
                trade = await create_trade(trade_data)
                trades_executed.append({
                    "trade_id": trade.id,
                    "token": opp["symbol"],
                    "amount": trade_amount,
                    "signal_score": opp["signal_score"]
                })
                
                # Add to active tokens to prevent duplicates
                active_trade_tokens.add(opp["address"])
                
                auto_trading_state["trades_executed"] += 1
                
                # Log each trade
                current_open = portfolio.open_trades + len(trades_executed)
                logger.info(f"✅ AUTO TRADE EXECUTED | token: {opp['symbol']} | {trade_amount:.4f} SOL | active_trades: {current_open}/{max_trades}")
                
            except Exception as e:
                logger.error(f"Trade execution error for {opp['symbol']}: {e}")
        
        if not trades_executed:
            return {"executed": False, "reason": "No trades executed (all filtered)", "scan_count": auto_trading_state["scan_count"]}
        
        return {
            "executed": True,
            "trades_count": len(trades_executed),
            "trades": trades_executed,
            "paper_trade": is_paper,
            "available_slots_remaining": available_slots - len(trades_executed)
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
    ⚡ SNIPER MICRO-TRADE SIZING ⚡
    
    For sniper mode: use 0.3%-1% of wallet per trade (micro positions)
    trade_size = wallet_balance * micro_trade_percent
    
    Ensures many small trades instead of few large ones.
    """
    # Use user's max_parallel_trades setting
    max_trades = min(settings.max_parallel_trades, ENGINE_CONFIG["max_open_trades"])
    open_trades = portfolio.open_trades
    remaining_slots = max(1, max_trades - open_trades)
    
    # Get available capital
    available = portfolio.available_sol
    wallet_balance = portfolio.wallet_balance_sol if portfolio.wallet_balance_sol > 0 else available
    
    # SNIPER MODE: Use micro-trade percent from config
    micro_percent = ENGINE_CONFIG.get("micro_trade_percent", 0.5) / 100
    micro_size = wallet_balance * micro_percent
    
    # Dynamic allocation as backup
    dynamic_size = available / remaining_slots
    
    # Use the SMALLER of: micro-size, dynamic allocation, or max limits
    max_micro = ENGINE_CONFIG.get("max_micro_trade_sol", 0.05)
    min_micro = ENGINE_CONFIG.get("min_micro_trade_sol", 0.005)
    
    # Apply user limits as well
    max_trade_by_percent = settings.total_budget_sol * (settings.max_trade_percent / 100)
    max_trade = min(max_trade_by_percent, settings.max_trade_amount_sol, max_micro)
    min_trade = max(settings.min_trade_sol, min_micro)
    
    # Final trade size: prefer micro-size for sniper mode
    trade_size = min(max_trade, max(min_trade, min(micro_size, dynamic_size)))
    
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
    ⚡ ULTRA-FAST SNIPER BOT ⚡
    - Sub-second scanning (0.8s intervals)
    - Multi-source scanner (7 DEX sources)
    - Processes 1500+ tokens per scan
    - Manages 100 simultaneous micro-trades
    - New token detection (< 2 minutes = priority)
    - Momentum scoring: vol*0.30 + buyers*0.25 + price*0.20 + accel*0.15 + age*0.10
    - Target: 8% profit, 6% stop loss, micro positions (0.5% of wallet)
    """
    global auto_trading_state
    
    logger.info("=" * 60)
    logger.info("🚀 HIGH-FREQUENCY MOMENTUM SCALPING ENGINE ACTIVATED 🚀")
    logger.info("=" * 60)
    logger.info(f"   🔄 Scan interval: {ENGINE_CONFIG['scan_interval_seconds']}s")
    logger.info(f"   📊 Max tokens/scan: {ENGINE_CONFIG['max_tokens_per_scan']}")
    logger.info(f"   💰 Max parallel trades: {ENGINE_CONFIG['max_open_trades']}")
    logger.info(f"   🎯 Take profit: {ENGINE_CONFIG['take_profit_percent']}%")
    logger.info(f"   🛡️ Stop loss: {ENGINE_CONFIG['stop_loss_percent']}%")
    logger.info(f"   🆕 New token bonus: +{ENGINE_CONFIG.get('new_token_priority_bonus', 30)} (< {ENGINE_CONFIG.get('new_token_age_seconds', 120)}s)")
    logger.info(f"   ⏱️ Cooldown: {ENGINE_CONFIG.get('signal_cooldown_seconds', 60)}s")
    logger.info(f"   📡 Sources: {', '.join(ENGINE_CONFIG['scanner_sources'])}")
    
    scan_start_time = datetime.now(timezone.utc)
    last_state_save = datetime.now(timezone.utc)
    
    # Log bot start to activity feed
    activity_feed.add_event("INFO", "SYSTEM", {
        "message": "🚀 High-Frequency Momentum Scalper gestartet"
    })
    
    while auto_trading_state["is_running"]:
        cycle_start = datetime.now(timezone.utc)
        
        try:
            settings = await get_bot_settings()
            portfolio = await get_portfolio_summary()
            
            # Save state every 30 seconds for crash recovery
            if (cycle_start - last_state_save).total_seconds() >= 30:
                await crash_recovery.save_state()
                last_state_save = cycle_start
            
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
            
            # SCAN
            logger.info(f"🔍 SCAN #{auto_trading_state['scan_count']+1} | Open: {open_trades}/{ENGINE_CONFIG['max_open_trades']} | Slots: {available_slots}")
            
            # Use multi-source scanner to get tokens from all DEX sources
            all_pairs_list = await multi_source_scanner.scan_all_sources()
            
            # Convert to dict for deduplication
            all_pairs = {}
            for pair in all_pairs_list:
                if len(all_pairs) >= ENGINE_CONFIG["max_tokens_per_scan"]:
                    break
                    
                address = pair.get("baseToken", {}).get("address", "")
                if not address or address in all_pairs:
                    continue
                    
                liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
                
                # Pre-filter: liquidity OR volume threshold
                if liquidity >= ENGINE_CONFIG["min_liquidity_usd"] or volume_24h >= ENGINE_CONFIG["min_volume_usd"]:
                    all_pairs[address] = pair
            
            # MOMENTUM SIGNAL ANALYSIS
            opportunities = []
            signals_processed = 0
            
            # Debug counters
            rejected_risk = 0
            rejected_signal_score = 0
            rejected_no_momentum = 0
            
            # Top momentum tokens for logging
            top_momentum = []
            
            for address, pair in all_pairs.items():
                try:
                    signals_processed += 1
                    
                    # Calculate momentum score using new v2 scoring
                    momentum_data = calculate_momentum_score_v2(pair)
                    
                    # Also calculate legacy momentum for compatibility
                    (
                        legacy_score, signal_strength, signals, signal_reasons,
                        buy_signal, buys_5m, sells_5m, volume_5m, price_5m, price_1h
                    ) = calculate_enhanced_momentum(pair, settings)
                    
                    # Risk analysis
                    risk_analysis = calculate_risk_analysis(pair, settings)
                    if not risk_analysis.passed_filters:
                        rejected_risk += 1
                        continue
                    
                    # Use new momentum score
                    signal_score = momentum_data["score"]
                    
                    # Check if momentum signal triggers
                    if not momentum_data["is_momentum"] and signal_score < ENGINE_CONFIG["min_signal_score"]:
                        rejected_no_momentum += 1
                        continue
                    
                    # Build opportunity
                    base_token = pair.get("baseToken", {})
                    liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                    
                    opportunity = {
                        "address": address,
                        "symbol": base_token.get("symbol", "???"),
                        "name": base_token.get("name", "Unknown"),
                        "price_usd": float(pair.get("priceUsd", 0) or 0),
                        "momentum_score": signal_score,
                        "signal_score": signal_score,
                        "momentum_data": momentum_data,
                        "signal_strength": signal_strength,
                        "signal_reasons": momentum_data.get("signal_reasons", []),
                        "risk_score": risk_analysis.risk_score,
                        "liquidity": liq,
                        "volume_5m": volume_5m,
                        "volume_growth": momentum_data["volume_growth"],
                        "price_change_1m": momentum_data.get("price_change_1m", 0),
                        "price_change_5m": momentum_data.get("price_change_5m", 0),
                        "buy_sell_ratio": momentum_data["buy_sell_ratio"],
                        "buys_1m": momentum_data.get("buys_1m", 0),
                        "sells_1m": momentum_data.get("sells_1m", 0),
                        "age_seconds": momentum_data.get("age_seconds", 999999),
                        "age_bonus": momentum_data.get("age_bonus", 0),
                        "is_new_token": momentum_data.get("is_new_token", False),
                        "pair_address": pair.get("pairAddress"),
                        "source": pair.get("source", "unknown"),
                        "is_momentum": momentum_data["is_momentum"],
                        "queued_at": datetime.now(timezone.utc).isoformat()
                    }
                    opportunities.append(opportunity)
                    
                    # Track top momentum for logging
                    top_momentum.append({
                        "symbol": opportunity["symbol"],
                        "score": signal_score,
                        "price_change": momentum_data.get("price_change_1m", 0),
                        "volume_growth": momentum_data["volume_growth"],
                        "age_seconds": momentum_data.get("age_seconds", 999999),
                        "is_new": momentum_data.get("is_new_token", False)
                    })
                        
                except Exception as e:
                    continue
            
            # Sort by momentum score (highest first)
            opportunities.sort(key=lambda x: x["signal_score"], reverse=True)
            top_momentum.sort(key=lambda x: x["score"], reverse=True)
            
            # Count new tokens
            new_tokens_count = sum(1 for opp in opportunities if opp.get("is_new_token"))
            
            # Update state
            auto_trading_state["last_scan"] = datetime.now(timezone.utc).isoformat()
            auto_trading_state["scan_count"] += 1
            auto_trading_state["signals_processed"] += signals_processed
            auto_trading_state["current_opportunities"] = opportunities[:10]
            
            # Calculate signals per minute
            elapsed_minutes = (datetime.now(timezone.utc) - scan_start_time).total_seconds() / 60
            if elapsed_minutes > 0:
                auto_trading_state["signals_per_minute"] = auto_trading_state["signals_processed"] / elapsed_minutes
            
            # LOG SCANNER SUMMARY
            logger.info(f"📊 SCANNER SUMMARY | tokens_scanned: {len(all_pairs)} | opportunities: {len(opportunities)} | open_trades: {open_trades}")
            
            # LOG TOP MOMENTUM TOKENS (include age info)
            if top_momentum[:5]:
                top_5_list = []
                for i, t in enumerate(top_momentum[:5]):
                    age_tag = "🆕" if t.get("is_new") else ""
                    age_s = t.get("age_seconds", 0)
                    age_str = f"{int(age_s)}s" if age_s < 300 else f"{int(age_s/60)}m"
                    top_5_list.append(f"{i+1}. {age_tag}{t['symbol']} score={t['score']:.0f} ({age_str})")
                logger.info(f"🔥 TOP MOMENTUM | " + " | ".join(top_5_list))
            
            # Execute trades for available slots
            # Use user's max_parallel_trades setting (respecting system max)
            max_parallel = min(settings.max_parallel_trades, ENGINE_CONFIG["max_open_trades"])
            available_slots = max_parallel - open_trades
            
            trades_executed_this_cycle = 0
            max_trades_per_token = ENGINE_CONFIG.get("max_trades_per_token", 1)
            
            # Track tokens we're trading in this cycle to avoid duplicates
            active_trade_tokens = set()
            
            # Get existing open trade tokens
            existing_open_trades = await db.trades.find(
                {"status": "OPEN"}, 
                {"token_address": 1, "_id": 0}
            ).to_list(100)
            for t in existing_open_trades:
                active_trade_tokens.add(t.get("token_address"))
            
            # Debug logging as requested
            logger.info(f"🔄 MULTI TRADE LOOP | opportunities={len(opportunities)} | open_trades={open_trades} | slots={available_slots}")
            
            if available_slots <= 0:
                logger.info(f"⚠️ No slots available (max_parallel_trades={max_parallel}, open={open_trades})")
                await asyncio.sleep(ENGINE_CONFIG["scan_interval_seconds"])
                continue
            
            for opp in opportunities:
                # Check if we've filled all available slots
                if trades_executed_this_cycle >= available_slots:
                    logger.info(f"🛑 Max trades reached for this cycle ({trades_executed_this_cycle}/{available_slots})")
                    break
                
                try:
                    token_address = opp["address"]
                    
                    # DUPLICATE PROTECTION: Skip if we already have a trade for this token
                    if token_address in active_trade_tokens:
                        logger.debug(f"⏭️ Skipping {opp['symbol']}: already trading this token")
                        continue
                    
                    # Double-check database for existing trades (safety check)
                    existing_count = await db.trades.count_documents({
                        "token_address": token_address,
                        "status": "OPEN"
                    })
                    if existing_count >= max_trades_per_token:
                        logger.debug(f"⏭️ Skipping {opp['symbol']}: max trades per token reached")
                        continue
                    
                    # COOLDOWN CHECK: Skip if token is in cooldown
                    if check_signal_cooldown(token_address):
                        logger.debug(f"⏭️ Skipping {opp['symbol']}: in cooldown")
                        continue
                    
                    # Calculate trade size dynamically
                    trade_amount = calculate_dynamic_trade_size(portfolio, settings)
                    
                    # Debug: Log the calculated trade amount
                    max_trade_limit = min(
                        settings.total_budget_sol * (settings.max_trade_percent / 100),
                        settings.max_trade_amount_sol
                    )
                    logger.debug(f"📊 Trade sizing: calculated={trade_amount:.4f}, max_allowed={max_trade_limit:.4f}, available={portfolio.available_sol:.4f}")
                    
                    # Ensure trade_amount doesn't exceed max
                    trade_amount = min(trade_amount, max_trade_limit)
                    
                    if trade_amount < settings.min_trade_sol:
                        logger.debug(f"⏭️ Skipping {opp['symbol']}: trade amount {trade_amount} < min {settings.min_trade_sol}")
                        continue
                    
                    # Execute trade
                    trade_data = TradeCreate(
                        token_address=token_address,
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
                    
                    # Add to active tokens to prevent duplicates in this cycle
                    active_trade_tokens.add(token_address)
                    
                    # Decrement available slots
                    available_slots -= 1
                    
                    # Set cooldown for this token
                    set_signal_cooldown(token_address)
                    
                    # Log to enhanced activity feed
                    activity_feed.log_bot_buy(
                        token=opp['symbol'],
                        price=opp["price_usd"],
                        amount_sol=trade_amount,
                        signal_score=int(opp['signal_score']),
                        reasons=opp.get('signal_reasons', [])
                    )
                    
                    # TRADE EXECUTED LOG
                    current_open = open_trades + trades_executed_this_cycle
                    logger.info(f"✅ TRADE EXECUTED | token: {opp['symbol']} | size: {trade_amount:.4f} SOL | score={opp['signal_score']:.0f} | target_profit: {ENGINE_CONFIG['take_profit_percent']}%")
                    
                except Exception as e:
                    logger.error(f"Trade execution error for {opp.get('symbol', '???')}: {e}")
            
            # Queue remaining opportunities
            remaining_opps = opportunities[available_slots:available_slots + 20]  # Queue up to 20
            for opp in remaining_opps:
                if len(auto_trading_state["signal_queue"]) < ENGINE_CONFIG.get("queue_max_size", 100):
                    # Don't queue duplicates or tokens in cooldown
                    if not any(q["address"] == opp["address"] for q in auto_trading_state["signal_queue"]):
                        if not check_signal_cooldown(opp["address"]):
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
    """
    Start the high-capacity multi-trade engine.
    
    INITIALIZATION ORDER:
    1. Check if already running
    2. Reset daily metrics
    3. Verify RPC connection
    4. Verify wallet sync status (if connected)
    5. Start trading engine
    """
    global auto_trading_state, auto_trading_task
    
    if auto_trading_state["is_running"]:
        return {"success": False, "message": "Auto trading already running"}
    
    # Reset daily metrics if new day
    today = datetime.now(timezone.utc).date().isoformat()
    if auto_trading_state.get("last_reset_date") != today:
        auto_trading_state["trades_today"] = 0
        auto_trading_state["daily_pnl"] = 0.0
        auto_trading_state["last_reset_date"] = today
    
    # Step 1: Verify RPC Connection
    logger.info("🔌 Verifying RPC connection before start...")
    if not rpc_state.get("connected"):
        rpc_result = await get_working_rpc()
        if not rpc_state.get("connected"):
            logger.warning("⚠️ RPC not connected, attempting failover...")
            # RPC failover is handled automatically
    
    if rpc_state.get("connected"):
        logger.info(f"RPC_CONNECTED: {rpc_state.get('current_endpoint', 'unknown')[:30]}...")
    else:
        logger.warning("⚠️ Starting in degraded mode - RPC not available")
    
    # Step 2: Check wallet sync status using WalletSyncManager
    can_start, block_reason = wallet_sync_manager.can_start_auto_trading()
    wallet_synced = wallet_state.get("sync_status") == "synced"
    wallet_address = wallet_state.get("address")
    
    # Log wallet status
    if wallet_synced:
        logger.info(f"WALLET_SYNCED: {wallet_address[:12]}... = {wallet_state.get('balance_sol', 0):.4f} SOL")
        logger.info(f"TRADING_ENGINE_WALLET: {wallet_address}")
    else:
        logger.info("ℹ️ No wallet connected - using paper trading budget")
    
    # Step 3: Get bot settings to check test mode
    settings = await get_bot_settings()
    test_mode = settings.paper_mode
    
    # In live mode (not test), require wallet sync
    if not test_mode and not wallet_synced:
        logger.error("AUTO_TRADING_BLOCKED_WALLET_SYNC_FAILED: Live mode requires synced wallet")
        return {
            "success": False,
            "message": "Live trading requires a synced wallet. Please connect your wallet first.",
            "error_code": "WALLET_NOT_SYNCED",
            "wallet_status": {
                "synced": False,
                "sync_status": wallet_state.get("sync_status"),
                "sync_error": wallet_state.get("sync_error")
            }
        }
    
    if test_mode:
        logger.info("TEST_MODE_ACTIVE: Transactions will be simulated")
        activity_feed.add_event("INFO", "SYSTEM", {
            "message": "🧪 Test mode active - no real transactions"
        })
    
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
    logger.info("TRADING_ENGINE_INITIALIZED")
    
    return {
        "success": True, 
        "message": "High-capacity trading engine started",
        "wallet_status": {
            "synced": wallet_synced,
            "address": wallet_address[:12] + "..." if wallet_address else None,
            "balance": wallet_state.get("balance_sol", 0) if wallet_synced else None
        },
        "rpc_status": {
            "connected": rpc_state.get("connected", False),
            "endpoint": rpc_state.get("current_endpoint", "none")[:30] + "..." if rpc_state.get("current_endpoint") else None
        },
        "test_mode": test_mode,
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


@api_router.post("/auto-trading/force-restart")
async def force_restart_auto_trading(background_tasks: BackgroundTasks):
    """Force restart the auto trading engine - clears any stuck state"""
    global auto_trading_state, auto_trading_task
    
    logger.info("⚠️ FORCE RESTART: Clearing auto trading state...")
    
    # Force stop any existing task
    if auto_trading_task:
        auto_trading_task.cancel()
        try:
            await auto_trading_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Error cancelling task: {e}")
        auto_trading_task = None
    
    # Force reset state
    auto_trading_state["is_running"] = False
    auto_trading_state["is_paused"] = False
    auto_trading_state["pause_reason"] = None
    
    # Wait a moment
    await asyncio.sleep(0.5)
    
    # Now start fresh
    return await start_auto_trading(background_tasks)


@api_router.post("/auto-trading/reset")
async def reset_auto_trading_state():
    """Reset the auto trading state without starting - clears stuck states"""
    global auto_trading_state, auto_trading_task
    
    logger.info("🔄 RESET: Clearing auto trading state...")
    
    # Force stop any existing task
    if auto_trading_task:
        auto_trading_task.cancel()
        try:
            await auto_trading_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        auto_trading_task = None
    
    # Reset all state
    auto_trading_state["is_running"] = False
    auto_trading_state["is_paused"] = False
    auto_trading_state["pause_reason"] = None
    auto_trading_state["scan_count"] = 0
    auto_trading_state["trades_executed"] = 0
    auto_trading_state["signals_processed"] = 0
    auto_trading_state["signal_queue"] = []
    auto_trading_state["errors"] = []
    
    logger.info("✅ Auto trading state reset complete")
    return {"success": True, "message": "Auto trading state reset"}

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
    """Fetch trending Solana tokens from DEX Screener with rate limiting"""
    
    # Check cache first
    cached = token_cache.get()
    if cached:
        logger.info(f"📊 Using cached tokens: {len(cached)} pairs")
        return cached[:limit]
    
    all_pairs = []
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client_http:
            # Use search endpoint for diverse Solana tokens
            search_queries = ["solana", "sol meme"]
            
            for query in search_queries[:1]:  # Only 1 query to reduce rate limits
                try:
                    response = await client_http.get(
                        "https://api.dexscreener.com/latest/dex/search",
                        params={"q": query}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        pairs = data.get("pairs", [])
                        
                        for p in pairs:
                            if p.get("chainId") != "solana":
                                continue
                                
                            liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                            vol = float(p.get("volume", {}).get("h24", 0) or 0)
                            
                            # Skip unrealistic values
                            if liq > 100000000:
                                continue
                            
                            if liq >= 1000 or vol >= 100:
                                all_pairs.append(p)
                        
                        logger.info(f"📊 Search '{query}': {len(pairs)} pairs, {len(all_pairs)} valid")
                    elif response.status_code == 429:
                        logger.warning("DEX Screener rate limited (429)")
                        await asyncio.sleep(2)
                except Exception as e:
                    logger.warning(f"DEX search failed: {e}")
            
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
            
            # Cache the results
            token_cache.set(unique_pairs)
            
            logger.info(f"📊 Loaded {len(unique_pairs)} valid Solana pairs from DEX Screener")
            return unique_pairs[:limit]
            
    except Exception as e:
        logger.error(f"Error fetching DEX Screener data: {e}")
    return []

async def fetch_pump_fun_tokens() -> List[Dict]:
    """Fetch new tokens from Pump.fun and trending memes via DEX Screener"""
    all_pairs = []
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client_http:
            # Multiple search queries for diverse tokens
            queries = ["pump.fun", "meme solana", "degen SOL"]
            
            for query in queries:
                try:
                    response = await client_http.get(
                        "https://api.dexscreener.com/latest/dex/search",
                        params={"q": query}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        pairs = data.get("pairs", [])
                        for p in pairs:
                            if p.get("chainId") == "solana":
                                liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                                if 1000 <= liq < 100000000:
                                    all_pairs.append(p)
                    elif response.status_code == 429:
                        await asyncio.sleep(1)
                        break  # Stop on rate limit
                except Exception as e:
                    logger.warning(f"Pump query '{query}' failed: {e}")
                    continue
            
            # Deduplicate
            seen = set()
            unique = []
            for p in all_pairs:
                addr = p.get("baseToken", {}).get("address", "")
                if addr and addr not in seen:
                    seen.add(addr)
                    unique.append(p)
            
            logger.info(f"🚀 Loaded {len(unique)} Pump.fun/meme pairs")
            return unique[:50]
                
    except Exception as e:
        logger.error(f"Error fetching Pump.fun data: {e}")
    return []


# ============== HIGH-PERFORMANCE SCANNER V3 ==============

# Scanner Cache with TTL
class ScannerCache:
    """
    High-performance cache for API responses with 2-second TTL.
    Avoids redundant API calls and reduces rate limiting.
    """
    
    def __init__(self, ttl_seconds: float = 2.0):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        async with self._lock:
            if key in self._cache:
                age = time.time() - self._timestamps.get(key, 0)
                if age < self._ttl:
                    self._hits += 1
                    return self._cache[key]
                else:
                    # Expired, remove
                    del self._cache[key]
                    del self._timestamps[key]
            self._misses += 1
            return None
    
    async def set(self, key: str, value: Any):
        """Set cache value with timestamp"""
        async with self._lock:
            self._cache[key] = value
            self._timestamps[key] = time.time()
    
    async def clear(self):
        """Clear all cached data"""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 1),
            "cached_items": len(self._cache)
        }


class MultiSourceScanner:
    """
    HIGH-PERFORMANCE MULTI-SOURCE SCANNER V3
    
    Features:
    - Parallel async scanning across 7 DEX sources
    - 2-second cache to avoid rate limits
    - Batch processing for large token sets
    - Token deduplication by address
    - New token priority detection
    
    Target: 1000-5000 tokens per scan cycle in 0.8-1.2 seconds
    """
    
    def __init__(self):
        self.scan_stats = {
            "total_sources_scanned": 0,
            "tokens_found": 0,
            "tokens_after_dedup": 0,
            "opportunities": 0,
            "last_scan": None,
            "avg_scan_time_ms": 0,
            "scan_history": []  # Last 10 scan times
        }
        self.source_status = {}
        
        # Initialize cache with 2-second TTL
        self.cache = ScannerCache(ttl_seconds=2.0)
        
        # Batch processing config
        self.batch_size = 200
        
        # HTTP client pool for connection reuse
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create reusable HTTP client"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=15.0,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
            )
        return self._http_client
        
    async def scan_all_sources(self) -> List[Dict]:
        """
        HIGH-PERFORMANCE SCANNER V3
        
        Scans all 7 DEX sources in parallel with:
        - 2-second API response caching
        - Batch processing for enrichment
        - Performance metrics logging
        
        Target: 1000-5000 tokens in < 1.2 seconds
        """
        scan_start = time.time()
        all_tokens = []
        source_results = {}
        
        # Run ALL scans in PARALLEL using asyncio.gather
        logger.info("🔍 SCANNER V3: Starting high-performance parallel scan across 7 sources...")
        
        try:
            # Execute all source scanners in parallel
            results = await asyncio.gather(
                self._scan_with_cache("dexscreener", self.scan_dexscreener),
                self._scan_with_cache("birdeye", self.scan_birdeye),
                self._scan_with_cache("jupiter", self.scan_jupiter),
                self._scan_with_cache("raydium", self.scan_raydium_pools),
                self._scan_with_cache("orca", self.scan_orca_pools),
                self._scan_with_cache("meteora", self.scan_meteora_pools),
                self._scan_with_cache("pumpfun", self.scan_pumpfun_pairs),
                return_exceptions=True
            )
            
            source_names = ["dexscreener", "birdeye", "jupiter", "raydium", "orca", "meteora", "pumpfun"]
            
            for i, result in enumerate(results):
                source_name = source_names[i]
                if isinstance(result, Exception):
                    logger.warning(f"⚠️ Scanner error {source_name}: {str(result)[:50]}")
                    self.source_status[source_name] = {"healthy": False, "count": 0, "cached": False}
                elif isinstance(result, dict):
                    # Result includes cache info
                    tokens = result.get("tokens", [])
                    cached = result.get("cached", False)
                    source_results[source_name] = len(tokens)
                    all_tokens.extend(tokens)
                    self.source_status[source_name] = {
                        "healthy": True, 
                        "count": len(tokens),
                        "cached": cached
                    }
                elif isinstance(result, list):
                    source_results[source_name] = len(result)
                    all_tokens.extend(result)
                    self.source_status[source_name] = {"healthy": True, "count": len(result), "cached": False}
                else:
                    self.source_status[source_name] = {"healthy": False, "count": 0, "cached": False}
                    
        except Exception as e:
            logger.error(f"Multi-source scan error: {e}")
        
        # Phase 2: Deduplicate by token address
        dedup_start = time.time()
        unique_tokens = self.deduplicate_tokens(all_tokens)
        dedup_time = (time.time() - dedup_start) * 1000
        
        # Phase 3: Batch enrich tokens (if needed for large sets)
        enriched_tokens = await self._batch_enrich_tokens(unique_tokens)
        
        # Calculate scan metrics
        scan_time = time.time() - scan_start
        scan_time_ms = scan_time * 1000
        
        # Update scan history (keep last 10)
        self.scan_stats["scan_history"].append(scan_time_ms)
        if len(self.scan_stats["scan_history"]) > 10:
            self.scan_stats["scan_history"] = self.scan_stats["scan_history"][-10:]
        
        # Calculate rolling average
        avg_scan_time = sum(self.scan_stats["scan_history"]) / len(self.scan_stats["scan_history"])
        
        # Update stats
        self.scan_stats["total_sources_scanned"] = len([s for s in self.source_status.values() if s.get("healthy")])
        self.scan_stats["tokens_found"] = len(all_tokens)
        self.scan_stats["tokens_after_dedup"] = len(enriched_tokens)
        self.scan_stats["last_scan"] = datetime.now(timezone.utc).isoformat()
        self.scan_stats["avg_scan_time_ms"] = round(avg_scan_time, 1)
        
        # Get cache stats
        cache_stats = self.cache.get_stats()
        
        # ===== PERFORMANCE LOG (user-requested format) =====
        source_breakdown = " | ".join([f"{k}={v}" for k, v in source_results.items()])
        cached_sources = sum(1 for s in self.source_status.values() if s.get("cached"))
        
        logger.info("=" * 70)
        logger.info("📊 SCANNER PERFORMANCE")
        logger.info(f"   sources_scanned: {self.scan_stats['total_sources_scanned']}")
        logger.info(f"   raw_tokens: {len(all_tokens)}")
        logger.info(f"   tokens_after_dedup: {len(enriched_tokens)}")
        logger.info(f"   scan_time: {scan_time:.3f} seconds")
        logger.info(f"   dedup_time: {dedup_time:.1f}ms")
        logger.info(f"   avg_scan_time: {avg_scan_time:.1f}ms")
        logger.info(f"   cache_hits: {cache_stats['hits']} ({cache_stats['hit_rate']:.1f}%)")
        logger.info(f"   sources: {source_breakdown}")
        logger.info("=" * 70)
        
        return enriched_tokens
    
    async def _scan_with_cache(self, source_name: str, scan_func) -> Dict:
        """
        Execute scan with cache check.
        Returns cached data if available, otherwise fetches fresh data.
        """
        cache_key = f"scan_{source_name}"
        
        # Check cache first
        cached_data = await self.cache.get(cache_key)
        if cached_data is not None:
            return {"tokens": cached_data, "cached": True}
        
        # Fetch fresh data
        try:
            tokens = await scan_func()
            # Cache the result
            await self.cache.set(cache_key, tokens)
            return {"tokens": tokens, "cached": False}
        except Exception as e:
            logger.warning(f"Scan error {source_name}: {e}")
            return {"tokens": [], "cached": False}
    
    async def _batch_enrich_tokens(self, tokens: List[Dict]) -> List[Dict]:
        """
        Batch process tokens for enrichment.
        Processes in chunks of batch_size (200) to avoid overwhelming APIs.
        """
        if len(tokens) <= self.batch_size:
            # Small set, no batching needed
            return tokens
        
        # Process in batches
        enriched = []
        total_batches = (len(tokens) + self.batch_size - 1) // self.batch_size
        
        for i in range(0, len(tokens), self.batch_size):
            batch = tokens[i:i + self.batch_size]
            # For now, just pass through (can add enrichment logic here)
            # Future: Add price updates, holder data, etc.
            enriched.extend(batch)
            
            # Small yield to prevent blocking
            if i > 0 and i % (self.batch_size * 2) == 0:
                await asyncio.sleep(0)
        
        return enriched
    
    def deduplicate_tokens(self, tokens: List[Dict]) -> List[Dict]:
        """Remove duplicate tokens by address, keeping the one with most data"""
        unique_tokens = {}
        
        for token in tokens:
            address = token.get("baseToken", {}).get("address", "")
            if not address:
                continue
                
            if address not in unique_tokens:
                unique_tokens[address] = token
            else:
                # Keep the token with higher volume or more complete data
                existing = unique_tokens[address]
                existing_vol = float(existing.get("volume", {}).get("h24", 0) or 0)
                new_vol = float(token.get("volume", {}).get("h24", 0) or 0)
                if new_vol > existing_vol:
                    unique_tokens[address] = token
        
        return list(unique_tokens.values())
    
    async def scan_dexscreener(self) -> List[Dict]:
        """
        ENHANCED DexScreener Scanner for High-Frequency Trading
        
        Features:
        - Parallel query execution
        - Multiple endpoints for maximum coverage
        - Optimized for 500+ tokens per call
        """
        pairs = []
        seen_addresses = set()
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Multiple search queries for maximum coverage
                queries = [
                    "solana trending", "sol meme", "pump.fun", "raydium sol",
                    "solana new", "sol degen", "bonk", "wif", "jup sol",
                    "solana token", "sol pump", "meme sol", "solana defi",
                    "raydium new", "orca sol", "meteora sol"
                ]
                
                # Execute queries in parallel batches
                batch_size = 5
                for i in range(0, len(queries), batch_size):
                    batch_queries = queries[i:i + batch_size]
                    
                    async def fetch_query(q):
                        try:
                            resp = await client.get(
                                "https://api.dexscreener.com/latest/dex/search",
                                params={"q": q}
                            )
                            if resp.status_code == 200:
                                return resp.json().get("pairs", [])
                            elif resp.status_code == 429:
                                await asyncio.sleep(0.3)
                        except:
                            pass
                        return []
                    
                    # Parallel fetch for this batch
                    results = await asyncio.gather(*[fetch_query(q) for q in batch_queries])
                    
                    for result in results:
                        for p in result:
                            if p.get("chainId") == "solana":
                                addr = p.get("baseToken", {}).get("address", "")
                                if addr and addr not in seen_addresses:
                                    liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                                    if liq >= ENGINE_CONFIG["min_liquidity_usd"]:
                                        p["source"] = "dexscreener"
                                        pairs.append(p)
                                        seen_addresses.add(addr)
                
                # Fetch latest tokens endpoint
                try:
                    resp = await client.get(
                        "https://api.dexscreener.com/token-profiles/latest/v1",
                        params={"chainId": "solana"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for p in data if isinstance(data, list) else data.get("pairs", []):
                            if isinstance(p, dict) and p.get("chainId", "solana") == "solana":
                                addr = p.get("baseToken", {}).get("address", "") or p.get("tokenAddress", "")
                                if addr and addr not in seen_addresses:
                                    pairs.append({
                                        "chainId": "solana",
                                        "baseToken": {"address": addr, "symbol": p.get("symbol", "?"), "name": p.get("name", "Unknown")},
                                        "priceUsd": str(p.get("priceUsd", 0)),
                                        "liquidity": {"usd": float(p.get("liquidity", {}).get("usd", 0) if isinstance(p.get("liquidity"), dict) else 1000)},
                                        "volume": {"h24": 0, "m5": 0, "h1": 0},
                                        "priceChange": {"h24": 0, "m5": 0, "h1": 0},
                                        "txns": {"m5": {"buys": 0, "sells": 0}},
                                        "pairCreatedAt": p.get("pairCreatedAt", 0),
                                        "source": "dexscreener_new"
                                    })
                                    seen_addresses.add(addr)
                except Exception as e:
                    logger.debug(f"DexScreener latest endpoint error: {e}")
                
                # Fetch boosted tokens (trending)
                try:
                    resp = await client.get("https://api.dexscreener.com/token-boosts/top/v1")
                    if resp.status_code == 200:
                        data = resp.json()
                        for p in data if isinstance(data, list) else []:
                            if p.get("chainId") == "solana":
                                addr = p.get("tokenAddress", "")
                                if addr and addr not in seen_addresses:
                                    pairs.append({
                                        "chainId": "solana",
                                        "baseToken": {"address": addr, "symbol": "BOOST", "name": "Boosted Token"},
                                        "priceUsd": "0",
                                        "liquidity": {"usd": 5000},
                                        "volume": {"h24": 0, "m5": 0, "h1": 0},
                                        "priceChange": {"h24": 0, "m5": 0, "h1": 0},
                                        "txns": {"m5": {"buys": 0, "sells": 0}},
                                        "source": "dexscreener_boost"
                                    })
                                    seen_addresses.add(addr)
                except:
                    pass
                        
        except Exception as e:
            logger.debug(f"DexScreener scan error: {e}")
        
        logger.debug(f"DexScreener returned {len(pairs)} unique tokens")
        return pairs
    
    async def scan_birdeye(self) -> List[Dict]:
        """
        Birdeye-style Scanner using DexScreener (since Birdeye requires API key).
        Focuses on trending and high-volume tokens.
        """
        pairs = []
        seen_addresses = set()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Use DexScreener for Birdeye-like data (trending, volume sorted)
                queries = ["trending solana", "solana volume", "solana gainers", "hot sol"]
                
                async def fetch_birdeye_style(q):
                    try:
                        resp = await client.get(
                            "https://api.dexscreener.com/latest/dex/search",
                            params={"q": q}
                        )
                        if resp.status_code == 200:
                            return resp.json().get("pairs", [])
                    except:
                        pass
                    return []
                
                results = await asyncio.gather(*[fetch_birdeye_style(q) for q in queries])
                
                for result in results:
                    for p in result:
                        if p.get("chainId") == "solana":
                            addr = p.get("baseToken", {}).get("address", "")
                            if addr and addr not in seen_addresses:
                                liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                                if liq >= ENGINE_CONFIG["min_liquidity_usd"]:
                                    p["source"] = "birdeye"
                                    pairs.append(p)
                                    seen_addresses.add(addr)
                        
        except Exception as e:
            logger.debug(f"Birdeye-style scan error: {e}")
        
        logger.debug(f"Birdeye-style returned {len(pairs)} unique tokens")
        return pairs
    
    async def scan_jupiter(self) -> List[Dict]:
        """
        OPTIMIZED Jupiter Scanner for High-Frequency Trading
        
        Uses strict token list for verified, tradeable tokens only.
        Avoids loading the massive 'all' list for speed.
        """
        pairs = []
        seen_addresses = set()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Jupiter strict token list (verified tokens only)
                resp = await client.get("https://token.jup.ag/strict")
                if resp.status_code == 200:
                    tokens = resp.json()
                    
                    # Process top 300 Jupiter tokens (quality over quantity)
                    for t in tokens[:300]:
                        addr = t.get("address", "")
                        if addr and addr not in seen_addresses:
                            pair = {
                                "chainId": "solana",
                                "baseToken": {
                                    "address": addr,
                                    "symbol": t.get("symbol", ""),
                                    "name": t.get("name", "")
                                },
                                "priceUsd": "0",
                                "liquidity": {"usd": 10000},  # Jupiter tokens have liquidity
                                "volume": {"h24": 0, "m5": 0, "h1": 0},
                                "priceChange": {"h24": 0, "m5": 0, "h1": 0},
                                "txns": {"m5": {"buys": 0, "sells": 0}, "h1": {"buys": 0, "sells": 0}},
                                "source": "jupiter"
                            }
                            pairs.append(pair)
                            seen_addresses.add(addr)
                    
        except Exception as e:
            logger.debug(f"Jupiter scan error: {e}")
        
        logger.debug(f"Jupiter returned {len(pairs)} unique tokens")
        return pairs
    
    async def scan_raydium_pools(self) -> List[Dict]:
        """
        ENHANCED Raydium Scanner - Parallel query execution
        """
        pairs = []
        seen_addresses = set()
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Multiple Raydium queries - expanded
                queries = [
                    "raydium sol", "raydium meme", "raydium new",
                    "raydium pump", "raydium token", "raydium defi"
                ]
                
                # Execute all queries in parallel
                async def fetch_raydium(q):
                    try:
                        resp = await client.get(
                            "https://api.dexscreener.com/latest/dex/search",
                            params={"q": q}
                        )
                        if resp.status_code == 200:
                            return resp.json().get("pairs", [])
                    except:
                        pass
                    return []
                
                results = await asyncio.gather(*[fetch_raydium(q) for q in queries])
                
                for result in results:
                    for p in result:
                        if p.get("chainId") == "solana" and "raydium" in p.get("dexId", "").lower():
                            addr = p.get("baseToken", {}).get("address", "")
                            if addr and addr not in seen_addresses:
                                liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                                if liq >= ENGINE_CONFIG["min_liquidity_usd"]:
                                    p["source"] = "raydium"
                                    pairs.append(p)
                                    seen_addresses.add(addr)
                                    
        except Exception as e:
            logger.debug(f"Raydium scan error: {e}")
        
        logger.debug(f"Raydium returned {len(pairs)} unique tokens")
        return pairs
    
    async def scan_orca_pools(self) -> List[Dict]:
        """
        ENHANCED Orca Whirlpool Scanner - Parallel query execution
        """
        pairs = []
        seen_addresses = set()
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                queries = ["orca sol", "orca whirlpool", "orca meme", "orca token", "orca new"]
                
                async def fetch_orca(q):
                    try:
                        resp = await client.get(
                            "https://api.dexscreener.com/latest/dex/search",
                            params={"q": q}
                        )
                        if resp.status_code == 200:
                            return resp.json().get("pairs", [])
                    except:
                        pass
                    return []
                
                results = await asyncio.gather(*[fetch_orca(q) for q in queries])
                
                for result in results:
                    for p in result:
                        if p.get("chainId") == "solana" and "orca" in p.get("dexId", "").lower():
                            addr = p.get("baseToken", {}).get("address", "")
                            if addr and addr not in seen_addresses:
                                liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                                if liq >= ENGINE_CONFIG["min_liquidity_usd"]:
                                    p["source"] = "orca"
                                    pairs.append(p)
                                    seen_addresses.add(addr)
                                    
        except Exception as e:
            logger.debug(f"Orca scan error: {e}")
        
        logger.debug(f"Orca returned {len(pairs)} unique tokens")
        return pairs
    
    async def scan_meteora_pools(self) -> List[Dict]:
        """
        ENHANCED Meteora DLMM Scanner - Parallel query execution
        """
        pairs = []
        seen_addresses = set()
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                queries = ["meteora sol", "meteora dlmm", "meteora new", "meteora meme", "meteora token"]
                
                async def fetch_meteora(q):
                    try:
                        resp = await client.get(
                            "https://api.dexscreener.com/latest/dex/search",
                            params={"q": q}
                        )
                        if resp.status_code == 200:
                            return resp.json().get("pairs", [])
                    except:
                        pass
                    return []
                
                results = await asyncio.gather(*[fetch_meteora(q) for q in queries])
                
                for result in results:
                    for p in result:
                        if p.get("chainId") == "solana" and "meteora" in p.get("dexId", "").lower():
                            addr = p.get("baseToken", {}).get("address", "")
                            if addr and addr not in seen_addresses:
                                liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                                if liq >= ENGINE_CONFIG["min_liquidity_usd"]:
                                    p["source"] = "meteora"
                                    pairs.append(p)
                                    seen_addresses.add(addr)
                                    
        except Exception as e:
            logger.debug(f"Meteora scan error: {e}")
        
        logger.debug(f"Meteora returned {len(pairs)} unique tokens")
        return pairs
    
    async def scan_pumpfun_pairs(self) -> List[Dict]:
        """
        ENHANCED Pump.fun Scanner for New Token Detection
        
        Focuses on finding the newest token launches with priority.
        """
        pairs = []
        seen_addresses = set()
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Multiple queries for pump.fun tokens - expanded
                queries = [
                    "pump.fun", "pumpfun", "bonding curve", "pump sol", "pump meme",
                    "pump new", "solana pump", "pump token", "pumpfun new"
                ]
                
                async def fetch_pumpfun(q):
                    try:
                        resp = await client.get(
                            "https://api.dexscreener.com/latest/dex/search",
                            params={"q": q}
                        )
                        if resp.status_code == 200:
                            return resp.json().get("pairs", [])
                    except:
                        pass
                    return []
                
                results = await asyncio.gather(*[fetch_pumpfun(q) for q in queries])
                
                for result in results:
                    for p in result:
                        if p.get("chainId") == "solana":
                            addr = p.get("baseToken", {}).get("address", "")
                            if addr and addr not in seen_addresses:
                                liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                                if liq >= ENGINE_CONFIG["min_liquidity_usd"]:
                                    # Mark as pump.fun source with creation time
                                    p["source"] = "pumpfun"
                                    pairs.append(p)
                                    seen_addresses.add(addr)
                                    
        except Exception as e:
            logger.debug(f"Pump.fun scan error: {e}")
        
        logger.debug(f"Pump.fun returned {len(pairs)} unique tokens")
        return pairs


# Global scanner instance
multi_source_scanner = MultiSourceScanner()


def calculate_momentum_score_v2(pair: Dict) -> dict:
    """
    HIGH-FREQUENCY MOMENTUM SCALPING SCORE
    
    Score formula (optimized for 1-minute signals):
    score = (volume_growth * 0.35) + (buyers_1m * 0.25) + (price_change_1m * 0.20) + (price_acceleration * 0.20)
    
    New tokens (< 120s) receive +30 priority bonus.
    
    Returns dict with score and breakdown.
    """
    # Extract data
    volume_5m = float(pair.get("volume", {}).get("m5", 0) or 0)
    volume_1h = float(pair.get("volume", {}).get("h1", 0) or 0)
    volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
    
    price_change_5m = float(pair.get("priceChange", {}).get("m5", 0) or 0)
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
    
    # Estimate 1-minute values from 5-minute data
    price_change_1m = price_change_5m / 3 if price_change_5m > 0 else price_change_5m
    volume_1m = volume_5m / 5 if volume_5m > 0 else 0
    
    txns = pair.get("txns", {})
    buys_5m = txns.get("m5", {}).get("buys", 0) or 0
    sells_5m = txns.get("m5", {}).get("sells", 0) or 0
    buys_1m = max(1, buys_5m // 5)  # Estimate 1-minute buyers
    sells_1m = max(1, sells_5m // 5)
    
    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    
    # Calculate TOKEN AGE
    created_at = pair.get("pairCreatedAt", 0)
    if created_at:
        age_seconds = (datetime.now(timezone.utc).timestamp() * 1000 - created_at) / 1000
    else:
        age_seconds = 999999  # Unknown age = old
    
    # ===== MOMENTUM SCORING (Weighted Formula) =====
    
    # 1. Volume Growth Score (35% weight = 0-35 points)
    baseline_1m = volume_1h / 60 if volume_1h > 0 else 1
    volume_growth = (volume_1m / baseline_1m) if baseline_1m > 0 else 0
    volume_score = min(35, volume_growth * 12)  # 3x growth = 35 points
    
    # 2. Buyer Activity Score (25% weight = 0-25 points)
    buyer_score = min(25, buys_1m * 5)  # 5 buyers/min = 25 points
    
    # 3. Price Momentum Score (20% weight = 0-20 points)
    if price_change_1m >= 5:
        price_score = 20
    elif price_change_1m >= 3:
        price_score = 16
    elif price_change_1m >= 2:
        price_score = 12
    elif price_change_1m >= 1:
        price_score = 8
    elif price_change_1m >= 0:
        price_score = 4
    else:
        price_score = 0
    
    # 4. Price Acceleration Score (20% weight = 0-20 points)
    price_accel = 0
    if price_change_1h != 0:
        accel_ratio = abs(price_change_5m) / max(abs(price_change_1h), 1)
        if accel_ratio >= 0.8:
            price_accel = 20
        elif accel_ratio >= 0.5:
            price_accel = 15
        elif accel_ratio >= 0.3:
            price_accel = 10
        elif accel_ratio >= 0.1:
            price_accel = 5
    
    # ===== BASE SCORE (0-100) =====
    base_score = volume_score + buyer_score + price_score + price_accel
    
    # ===== NEW TOKEN PRIORITY BONUS =====
    age_bonus = 0
    if age_seconds < ENGINE_CONFIG.get("ultra_new_token_seconds", 60):
        age_bonus = ENGINE_CONFIG.get("ultra_new_token_bonus", 50)  # Ultra-new: +50
    elif age_seconds < ENGINE_CONFIG.get("new_token_age_seconds", 120):
        age_bonus = ENGINE_CONFIG.get("new_token_priority_bonus", 30)  # New: +30
    elif age_seconds < 300:  # < 5 minutes
        age_bonus = 15
    elif age_seconds < 600:  # < 10 minutes
        age_bonus = 8
    elif age_seconds < 3600:  # < 1 hour
        age_bonus = 3
    
    # ===== ADDITIONAL BONUSES =====
    bonus = 0
    
    # Buy/sell pressure bonus (momentum entry signal)
    buy_sell_ratio = buys_1m / max(sells_1m, 1)
    if buy_sell_ratio >= 2.0:
        bonus += 10
    elif buy_sell_ratio >= 1.5:
        bonus += 7
    elif buy_sell_ratio >= 1.05:
        bonus += 3
    
    # Early pump detection bonus
    if price_change_1m >= ENGINE_CONFIG.get("momentum_price_change_min", 2) and volume_growth >= ENGINE_CONFIG.get("momentum_volume_multiplier", 1.5):
        bonus += 15  # Strong momentum signal
    
    # Add age bonus for priority ranking
    bonus += age_bonus
    
    # ===== TOTAL SCORE =====
    total_score = base_score + bonus
    
    # Determine if this is a MOMENTUM opportunity (entry conditions)
    # price_change_1m >= 2% AND volume_1m >= 1.5x baseline AND buyers >= sellers
    is_momentum = (
        price_change_1m >= ENGINE_CONFIG.get("min_price_change_1m", 2) and
        volume_growth >= ENGINE_CONFIG.get("momentum_volume_multiplier", 1.5) and
        buys_1m >= sells_1m
    )
    
    # Build signal reasons
    signal_reasons = []
    if age_seconds < 120:
        signal_reasons.append(f"🆕 NEW ({int(age_seconds)}s)")
    if price_change_1m >= 2:
        signal_reasons.append(f"📈 +{price_change_1m:.1f}%/1m")
    if volume_growth >= 1.5:
        signal_reasons.append(f"📊 {volume_growth:.1f}x vol")
    if buy_sell_ratio >= 1.05:
        signal_reasons.append(f"🔥 {buy_sell_ratio:.1f}x buys")
    
    return {
        "score": round(total_score, 1),
        "base_score": round(base_score, 1),
        "volume_score": round(volume_score, 1),
        "buyer_score": round(buyer_score, 1),
        "price_score": round(price_score, 1),
        "price_accel": price_accel,
        "age_bonus": age_bonus,
        "age_seconds": int(age_seconds),
        "bonus": bonus,
        "volume_growth": round(volume_growth, 2),
        "buy_sell_ratio": round(buy_sell_ratio, 2),
        "price_change_1m": round(price_change_1m, 2),
        "price_change_5m": round(price_change_5m, 2),
        "buys_1m": buys_1m,
        "sells_1m": sells_1m,
        "is_momentum": is_momentum,
        "is_new_token": age_seconds < 120,
        "signal_reasons": signal_reasons
    }


def calculate_risk_analysis(pair: Dict, settings: BotSettings) -> TokenRiskAnalysis:
    """Calculate comprehensive risk analysis for a token - RELAXED FOR MEMECOINS"""
    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    volume = float(pair.get("volume", {}).get("h24", 0) or 0)
    price_change = float(pair.get("priceChange", {}).get("h24", 0) or 0)
    
    filter_reasons = []
    passed = True
    
    # Risk calculations - RELAXED THRESHOLDS for memecoins
    honeypot_risk = "LOW" if liquidity > 5000 else "MEDIUM" if liquidity > 500 else "HIGH"
    rugpull_risk = "LOW" if liquidity > 20000 else "MEDIUM" if liquidity > 2000 else "HIGH"
    liquidity_locked = liquidity > 10000
    
    # Simulated holder analysis - MORE PERMISSIVE
    dev_wallet_percent = 5.0 if liquidity > 10000 else 10.0 if liquidity > 2000 else 15.0
    top_holder_percent = 30.0 if volume > 20000 else 45.0 if volume > 2000 else 55.0
    
    # Apply filters - ONLY STRICT FILTER: min_liquidity
    if liquidity < settings.min_liquidity_usd:
        passed = False
        filter_reasons.append(f"Liquidity ${liquidity:.0f} < ${settings.min_liquidity_usd:.0f}")
    
    # REMOVED: Dev wallet and top holder filters - too restrictive for memecoins
    # These are now warnings only, not blockers
    
    # Only block on VERY HIGH honeypot risk (liquidity < $500)
    if honeypot_risk == "HIGH" and liquidity < 500:
        passed = False
        filter_reasons.append("Extreme honeypot risk (liquidity < $500)")
    
    # Calculate overall risk score (0-100, higher = riskier)
    risk_score = 20  # Lower base score
    if liquidity < 1000:
        risk_score += 30
    elif liquidity < 2000:
        risk_score += 20
    elif liquidity < 5000:
        risk_score += 10
    if volume < 500:
        risk_score += 15
    elif volume < 1000:
        risk_score += 10
    if abs(price_change) > 100:
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
async def scan_tokens(limit: int = 500):
    """Scan for new and trending tokens with full analysis - EXPANDED to 500 tokens"""
    settings = await get_bot_settings()
    
    # Get filter config at the start
    min_liq = ENGINE_CONFIG.get("min_liquidity_usd", 800)
    min_vol = ENGINE_CONFIG.get("min_volume_usd", 800)
    
    # Use multi-source scanner for maximum coverage
    all_pairs_list = await multi_source_scanner.scan_all_sources()
    
    # Also get legacy sources as backup
    pump_pairs = await fetch_pump_fun_tokens()
    dex_pairs = await fetch_dex_screener_tokens(200)
    
    # Combine all sources
    all_pairs = {}
    
    # Multi-source scanner results first (already deduplicated)
    for pair in all_pairs_list:
        address = pair.get("baseToken", {}).get("address", "")
        if not address:
            continue
        
        liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        vol_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
        
        # Skip unrealistic liquidity (>$100M for memecoins)
        if liq > 100000000:
            continue
        
        # RELAXED FILTER: Minimum liquidity $800 OR volume $800
        if liq >= min_liq or vol_24h >= min_vol:
            all_pairs[address] = pair
    
    # Add legacy sources
    for pair in dex_pairs + pump_pairs:
        address = pair.get("baseToken", {}).get("address", "")
        if not address or address in all_pairs:
            continue
        
        liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        vol_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
        
        if liq > 100000000:
            continue
        
        if liq >= min_liq or vol_24h >= min_vol:
            all_pairs[address] = pair
    
    logger.info(f"📊 Scanner API: {len(all_pairs)} tokens after filtering (min liq: ${min_liq}, min vol: ${min_vol})")
    
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
    token_symbol = trade.get('token_symbol', 'Unknown')
    logger.info(f"✅ [{mode_str}] Trade closed: {token_symbol} - PnL: {pnl_percent:.2f}% ({pnl_sol:.6f} SOL)")
    
    # Log TP/SL hit events
    if reason in ["TP_HIT", "TAKE_PROFIT"]:
        activity_feed.log_tp_hit(token_symbol, pnl_percent)
    elif reason in ["SL_HIT", "STOP_LOSS"]:
        activity_feed.log_sl_hit(token_symbol, pnl_percent)
    
    # Log sell to activity feed
    activity_feed.log_bot_sell(
        token=token_symbol,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl_sol=round(pnl_sol, 6),
        pnl_percent=round(pnl_percent, 2),
        reason=reason
    )
    
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


@api_router.post("/trades/update-all-prices")
async def update_all_trade_prices():
    """
    Bulk update current prices for all open trades.
    Fetches live prices from DEX Screener and updates each trade.
    Also checks TP/SL conditions and auto-closes if triggered.
    """
    open_trades = await db.trades.find({"status": "OPEN"}, {"_id": 0}).to_list(100)
    
    if not open_trades:
        return {"updated": 0, "closed": 0, "trades": []}
    
    # Collect unique token addresses - prefer base token address over pair address
    token_addresses = []
    for t in open_trades:
        # Try token_address first (base token), then pair_address
        addr = t.get("token_address") or t.get("pair_address")
        if addr and addr not in token_addresses:
            token_addresses.append(addr)
    
    # Fetch all prices in batch
    price_map = {}
    if token_addresses:
        # Filter out None values
        valid_addresses = [addr for addr in token_addresses if addr]
        
        if valid_addresses:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client_http:
                    # Batch request to DEX Screener (max 30 addresses per request)
                    for i in range(0, len(valid_addresses), 30):
                        batch = valid_addresses[i:i+30]
                        addresses_str = ",".join(batch)
                        
                        logger.info(f"📊 Fetching prices for {len(batch)} tokens: {batch}")
                        
                        response = await client_http.get(
                            f"https://api.dexscreener.com/latest/dex/tokens/{addresses_str}"
                        )
                        if response.status_code == 200:
                            data = response.json()
                            pairs = data.get("pairs") or []
                            
                            for pair in pairs:
                                pair_addr = pair.get("pairAddress", "")
                                base_addr = pair.get("baseToken", {}).get("address", "")
                                price = float(pair.get("priceUsd", 0) or 0)
                                
                                if price > 0:
                                    # Map both pair address and base token address
                                    if pair_addr:
                                        price_map[pair_addr] = price
                                    if base_addr:
                                        price_map[base_addr] = price
                            
                            logger.info(f"📊 Got {len(pairs)} pairs, mapped {len(price_map)} prices")
                        else:
                            logger.warning(f"DEX Screener returned {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching bulk prices: {e}")
    
    # Update each trade
    updated_count = 0
    closed_count = 0
    trade_updates = []
    settings = await get_bot_settings()
    
    for trade in open_trades:
        try:
            # Get current price
            pair_addr = trade.get("pair_address")
            token_addr = trade.get("token_address")
            current_price = price_map.get(pair_addr) or price_map.get(token_addr) or trade.get("price_current", 0)
            
            if current_price <= 0:
                continue
            
            # Calculate P&L
            entry_price = trade.get("price_entry", current_price)
            pnl_percent = ((current_price / entry_price) - 1) * 100 if entry_price > 0 else 0
            pnl_sol = trade.get("amount_sol", 0) * (pnl_percent / 100)
            
            # Check TP/SL - ensure None values are handled
            should_close = False
            close_reason = None
            
            tp_price = trade.get("take_profit") or 0
            sl_price = trade.get("stop_loss") or 0
            trailing = trade.get("trailing_stop") or 0
            
            if tp_price > 0 and current_price >= tp_price:
                should_close = True
                close_reason = "TP_HIT"
            elif sl_price > 0 and current_price <= sl_price:
                should_close = True
                close_reason = "SL_HIT"
            elif trailing > 0 and current_price <= trailing:
                should_close = True
                close_reason = "TRAILING_STOP"
            
            # Update trade
            update_data = {
                "price_current": current_price,
                "pnl": round(pnl_sol, 6),
                "pnl_percent": round(pnl_percent, 2)
            }
            
            # Update peak price for trailing stop
            peak = trade.get("price_peak") or entry_price
            if peak is not None and current_price > peak:
                update_data["price_peak"] = current_price
                # Activate trailing stop after 6% profit
                if pnl_percent >= ENGINE_CONFIG.get("trailing_stop_activation", 6):
                    new_trailing = current_price * (1 - settings.trailing_stop_percent / 100)
                    if new_trailing > (trailing or 0):
                        update_data["trailing_stop"] = new_trailing
            
            await db.trades.update_one({"id": trade["id"]}, {"$set": update_data})
            updated_count += 1
            
            trade_update = {
                "id": trade["id"],
                "symbol": trade.get("token_symbol", "???"),
                "price_current": current_price,
                "pnl": round(pnl_sol, 6),
                "pnl_percent": round(pnl_percent, 2),
                "should_close": should_close
            }
            trade_updates.append(trade_update)
            
            # Auto-close if TP/SL hit
            if should_close:
                try:
                    await close_trade(trade["id"], current_price, close_reason)
                    closed_count += 1
                    logger.info(f"📈 Auto-closed {trade.get('token_symbol')}: {close_reason} at {pnl_percent:.2f}%")
                except Exception as e:
                    logger.error(f"Error auto-closing trade: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating trade {trade.get('id', '?')}: {e}")
    
    logger.info(f"💹 Price update: {updated_count} trades updated, {closed_count} auto-closed")
    
    return {
        "updated": updated_count,
        "closed": closed_count,
        "trades": trade_updates
    }


# Signal cooldown tracker
signal_cooldowns = {}

def check_signal_cooldown(token_address: str) -> bool:
    """Check if token is in cooldown period"""
    if token_address in signal_cooldowns:
        cooldown_until = signal_cooldowns[token_address]
        if datetime.now(timezone.utc) < cooldown_until:
            return True  # Still in cooldown
    return False

def set_signal_cooldown(token_address: str):
    """Set cooldown for a token after trade execution"""
    cooldown_seconds = ENGINE_CONFIG.get("signal_cooldown_seconds", 60)
    signal_cooldowns[token_address] = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)

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
async def add_smart_wallet(address: str, name: str = None):
    """Add a wallet to track"""
    existing = await db.smart_wallets.find_one({"address": address})
    if existing:
        raise HTTPException(status_code=400, detail="Wallet already tracked")
    
    wallet = SmartWallet(address=address)
    doc = wallet.model_dump()
    doc["last_seen"] = doc["last_seen"].isoformat()
    if name:
        doc["name"] = name
    await db.smart_wallets.insert_one(doc)
    
    # Add to in-memory tracker
    smart_wallet_tracker.add_wallet(address, name)
    
    # Log to activity feed
    activity_feed.add_event("INFO", "WALLET", {
        "message": f"📋 Started tracking wallet: {address[:12]}..."
    })
    
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


# ============== SCANNER PERFORMANCE ENDPOINT ==============

@api_router.get("/scanner/stats")
async def get_scanner_stats():
    """
    Get High-Performance Scanner V3 statistics.
    
    Returns:
    - sources_scanned: Number of healthy sources
    - raw_tokens: Total tokens before deduplication
    - tokens_after_dedup: Unique tokens after deduplication
    - avg_scan_time_ms: Rolling average scan time
    - cache_stats: Cache hit rate and statistics
    - source_status: Health status per source
    """
    cache_stats = multi_source_scanner.cache.get_stats()
    
    return {
        "scanner_version": "v3",
        "stats": {
            **multi_source_scanner.scan_stats,
            "cache": cache_stats
        },
        "source_status": multi_source_scanner.source_status,
        "config": {
            "batch_size": multi_source_scanner.batch_size,
            "cache_ttl_seconds": multi_source_scanner.cache._ttl,
            "target_tokens_per_cycle": "1000-5000",
            "target_scan_interval": "0.8-1.2s"
        }
    }


@api_router.post("/scanner/clear-cache")
async def clear_scanner_cache():
    """Clear the scanner cache to force fresh API calls"""
    await multi_source_scanner.cache.clear()
    return {"success": True, "message": "Scanner cache cleared"}


# ============== ACTIVITY FEED ==============

@api_router.get("/activity")
async def get_activity_feed(limit: int = 50):
    """Get recent trading activity events"""
    return activity_feed.get_events(limit)


@api_router.post("/activity/clear")
async def clear_activity_feed():
    """Clear activity feed"""
    activity_feed.events = []
    return {"success": True}


# ============== EARLY PUMP DETECTION ENDPOINTS ==============

@api_router.get("/early-pumps")
async def get_early_pumps():
    """Get detected early pump tokens"""
    return {
        "detected_pumps": [
            {
                "address": addr,
                "detected_at": time.isoformat()
            }
            for addr, time in early_pump_detector.detected_pumps.items()
        ],
        "count": len(early_pump_detector.detected_pumps)
    }


@api_router.post("/scan-early-pumps")
async def scan_for_early_pumps():
    """Manually trigger early pump scan"""
    pump_pairs = await fetch_pump_fun_tokens()
    dex_pairs = await fetch_dex_screener_tokens(50)
    
    detected = []
    for pair in pump_pairs + dex_pairs:
        is_pump, confidence, reasons = early_pump_detector.check_early_pump(pair)
        if is_pump:
            token = pair.get("baseToken", {})
            detected.append({
                "symbol": token.get("symbol"),
                "address": token.get("address"),
                "confidence": confidence,
                "reasons": reasons,
                "price": pair.get("priceUsd"),
                "liquidity": pair.get("liquidity", {}).get("usd")
            })
            
            # Log to activity feed
            activity_feed.add_event("SIGNAL", token.get("symbol", "???"), {
                "signal_type": "EARLY_PUMP",
                "strength": "STRONG" if confidence >= 80 else "MEDIUM",
                "score": confidence,
                "message": f"🚀 Early pump detected: {token.get('symbol')} (Confidence: {confidence}%)"
            })
    
    return {
        "detected": detected,
        "total_scanned": len(pump_pairs) + len(dex_pairs)
    }


# ============== SMART WALLET TRACKER ENDPOINTS ==============

@api_router.delete("/smart-wallets/{address}")
async def remove_smart_wallet(address: str):
    """Remove a wallet from tracking"""
    await db.smart_wallets.update_one(
        {"address": address},
        {"$set": {"is_tracking": False}}
    )
    if address in smart_wallet_tracker.tracked_wallets:
        del smart_wallet_tracker.tracked_wallets[address]
    return {"success": True}


@api_router.get("/smart-wallets/copy-signals")
async def get_copy_signals():
    """Get pending copy trade signals"""
    return smart_wallet_tracker.get_pending_copy_signals()


# ============== API FAILOVER ENDPOINTS ==============

@api_router.get("/api-status")
async def get_api_status():
    """Get API health status"""
    return {
        "current_api": api_failover.get_healthy_api(),
        "status": api_failover.get_status()
    }


# ============== CRASH RECOVERY ENDPOINTS ==============

@api_router.post("/bot/save-state")
async def save_bot_state():
    """Manually save bot state"""
    await crash_recovery.save_state()
    return {"success": True, "message": "State saved"}


@api_router.get("/bot/recover-state")
async def get_recovery_state():
    """Get last saved state"""
    state = await crash_recovery.load_state()
    return state or {"message": "No saved state found"}


@api_router.post("/bot/recover")
async def trigger_recovery():
    """Trigger crash recovery"""
    recovered = await crash_recovery.check_and_recover()
    trades = await crash_recovery.recover_active_trades()
    return {
        "recovered": recovered,
        "active_trades_restored": len(trades)
    }


# ============== SYSTEM STATUS ENDPOINTS ==============

@api_router.get("/system/modules")
async def get_system_modules():
    """Get status of all trading modules"""
    return {
        "modules": {
            "market_scanner": {
                "status": "active" if auto_trading_state["is_running"] else "stopped",
                "interval_ms": ENGINE_CONFIG["scan_interval_seconds"] * 1000
            },
            "early_pump_detector": {
                "status": "active",
                "detected_count": len(early_pump_detector.detected_pumps)
            },
            "momentum_analyzer": {
                "status": "active",
                "min_score": ENGINE_CONFIG["min_signal_score"]
            },
            "smart_wallet_tracker": {
                "status": "active",
                "tracked_wallets": len(smart_wallet_tracker.tracked_wallets),
                "pending_signals": len(smart_wallet_tracker.get_pending_copy_signals())
            },
            "trade_monitor": {
                "status": "active",
                "interval_ms": ENGINE_CONFIG["price_update_interval"] * 1000
            },
            "risk_manager": {
                "status": "active",
                "max_trades": ENGINE_CONFIG["max_open_trades"],
                "daily_loss_limit": ENGINE_CONFIG["daily_loss_limit_percent"]
            },
            "api_failover": {
                "status": "active",
                "current_api": api_failover.get_healthy_api()
            },
            "crash_recovery": {
                "status": "active"
            }
        },
        "engine_config": ENGINE_CONFIG
    }


# ============== RPC CONNECTION MANAGER ==============

# Load Helius API key from environment (optional - use public RPCs as fallback)
HELIUS_API_KEY = os.environ.get('HELIUS_API_KEY', '')
HELIUS_RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY else None

# RPC Configuration with failover
# Priority: 1. Ankr (most reliable), 2. Solana Public, 3. Extrnode, 4. Helius (if key)
RPC_ENDPOINTS = [
    "https://rpc.ankr.com/solana",           # Primary - reliable free RPC
    "https://solana.public-rpc.com",         # Backup 1
    "https://api.mainnet-beta.solana.com",   # Backup 2 - official but rate limited
    "https://solana-mainnet.rpc.extrnode.com" # Backup 3
]

# Add Helius at front if API key provided (premium)
if HELIUS_RPC_URL and HELIUS_API_KEY:
    RPC_ENDPOINTS.insert(0, HELIUS_RPC_URL)

RPC_CONFIG = {
    "primary": RPC_ENDPOINTS[0],
    "endpoints": RPC_ENDPOINTS,
    "timeout": 15,                    # Increased from 10 to 15 seconds
    "retry_interval": 5,
    "max_retries": 3,
    "health_check_interval": 30,     # Check RPC health every 30 seconds
    "rate_limit_backoff": 2,         # Seconds to wait after rate limit
    "confirm_timeout": 60000         # Transaction confirmation timeout (ms)
}


# ============== NATIVE SOLANA CLIENT ==============

class SolanaClient:
    """
    Native Solana client using solana-py and solders.
    Provides direct blockchain interaction with proper keypair handling.
    """
    
    def __init__(self):
        self.client: Optional[AsyncClient] = None
        self.keypair: Optional[Keypair] = None
        # Use official Solana RPC as default (most reliable)
        self.current_rpc: str = "https://api.mainnet-beta.solana.com"
        self.initialized = False
    
    async def initialize(self, rpc_url: str = None):
        """Initialize the Solana async client"""
        if rpc_url:
            self.current_rpc = rpc_url
        
        try:
            self.client = AsyncClient(self.current_rpc, commitment=Commitment("confirmed"))
            
            # Test connection
            health = await self.client.is_connected()
            if health:
                logger.info(f"✅ SOLANA_CLIENT_CONNECTED: {self.current_rpc[:40]}...")
                self.initialized = True
                return {"success": True, "rpc": self.current_rpc}
            else:
                raise Exception("Connection health check failed")
                
        except Exception as e:
            logger.error(f"❌ SOLANA_CLIENT_INIT_FAILED: {e}")
            return {"success": False, "error": str(e)}
    
    async def switch_rpc(self, new_rpc: str):
        """Switch to a different RPC endpoint"""
        old_rpc = self.current_rpc
        self.current_rpc = new_rpc
        
        if self.client:
            await self.client.close()
        
        result = await self.initialize(new_rpc)
        if result["success"]:
            logger.info(f"🔄 RPC_SWITCHED: {old_rpc[:30]}... -> {new_rpc[:30]}...")
        return result
    
    def load_keypair_from_env(self) -> dict:
        """
        Load wallet keypair from SOLANA_PRIVATE_KEY environment variable.
        Supports both base58 and JSON array formats.
        """
        private_key_env = os.environ.get("SOLANA_PRIVATE_KEY")
        
        if not private_key_env:
            logger.info("ℹ️ No SOLANA_PRIVATE_KEY set - running in read-only mode")
            return {"success": False, "error": "No private key configured", "read_only": True}
        
        try:
            # Try base58 format first (most common)
            if not private_key_env.startswith("["):
                private_key_bytes = base58.b58decode(private_key_env)
                self.keypair = Keypair.from_bytes(private_key_bytes)
            else:
                # JSON array format
                key_array = json.loads(private_key_env)
                private_key_bytes = bytes(key_array)
                self.keypair = Keypair.from_bytes(private_key_bytes)
            
            pubkey = str(self.keypair.pubkey())
            logger.info(f"✅ KEYPAIR_LOADED: {pubkey[:12]}...{pubkey[-8:]}")
            
            return {
                "success": True,
                "pubkey": pubkey,
                "keypair_loaded": True
            }
            
        except Exception as e:
            logger.error(f"❌ KEYPAIR_LOAD_FAILED: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_balance(self, address: str = None) -> dict:
        """
        Get SOL balance for an address using native client.
        If no address provided, uses loaded keypair.
        """
        if not self.client or not self.initialized:
            await self.initialize()
        
        try:
            if address:
                pubkey = Pubkey.from_string(address)
            elif self.keypair:
                pubkey = self.keypair.pubkey()
            else:
                return {"success": False, "error": "No address or keypair available"}
            
            response = await self.client.get_balance(pubkey)
            
            if response.value is not None:
                balance_sol = response.value / 1e9
                logger.info(f"💰 BALANCE_FETCHED: {str(pubkey)[:12]}... = {balance_sol:.6f} SOL")
                return {
                    "success": True,
                    "balance_lamports": response.value,
                    "balance_sol": balance_sol,
                    "address": str(pubkey)
                }
            else:
                return {"success": False, "error": "Failed to fetch balance"}
                
        except Exception as e:
            logger.error(f"❌ BALANCE_FETCH_ERROR: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_slot(self) -> dict:
        """Get current slot for health check"""
        if not self.client or not self.initialized:
            await self.initialize()
        
        try:
            response = await self.client.get_slot()
            return {"success": True, "slot": response.value}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_recent_blockhash(self) -> dict:
        """Get recent blockhash for transactions"""
        if not self.client or not self.initialized:
            await self.initialize()
        
        try:
            response = await self.client.get_latest_blockhash()
            return {
                "success": True,
                "blockhash": str(response.value.blockhash),
                "last_valid_block_height": response.value.last_valid_block_height
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_token_accounts(self, address: str) -> dict:
        """Get SPL token accounts for a wallet"""
        if not self.client or not self.initialized:
            await self.initialize()
        
        try:
            pubkey = Pubkey.from_string(address)
            # Using httpx for token accounts query
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                response = await http_client.post(
                    self.current_rpc,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenAccountsByOwner",
                        "params": [
                            address,
                            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                            {"encoding": "jsonParsed"}
                        ]
                    }
                )
                data = response.json()
                if "result" in data:
                    return {"success": True, "accounts": data["result"]["value"]}
                return {"success": False, "error": data.get("error", {}).get("message", "Unknown")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_pubkey(self) -> Optional[str]:
        """Get public key if keypair is loaded"""
        if self.keypair:
            return str(self.keypair.pubkey())
        return None
    
    async def close(self):
        """Close the client connection"""
        if self.client:
            await self.client.close()
            self.initialized = False


# Initialize global Solana client
solana_client = SolanaClient()


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
    "failed_requests": 0,
    "network_available": True,
    "last_network_check": None,
    "rate_limited_until": None,
    "provider_status": {}  # Track status of each provider
}

# Network diagnostic results
network_diagnostic = {
    "outbound_available": None,
    "last_check": None,
    "error": None
}

# Wallet State Manager - synced with actual wallet balance
wallet_state = {
    "address": None,
    "balance_sol": 0.0,
    "last_update": None,
    "sync_status": "disconnected",  # disconnected, syncing, synced, error
    "sync_error": None,
    "validation_passed": False,
    "retry_count": 0,
    "last_sync_attempt": None,
    "public_key_valid": False,
    "wallet_type": None,  # phantom, solflare, backpack, server
    "adapter_conflict": False
}

# Wallet sync configuration
WALLET_SYNC_CONFIG = {
    "max_retries": 3,
    "retry_delay_seconds": 2,
    "min_balance_sol": 0.001,  # Minimum SOL for trading
    "sync_timeout_seconds": 30,
    "rpc_timeout_seconds": 10
}

# Environment variable requirements
REQUIRED_ENV_VARS = {
    "optional": ["PRIVATE_KEY", "SOLANA_RPC_URL"],  # Optional for browser wallet mode
    "required": ["MONGO_URL", "DB_NAME"]
}


class WalletSyncError(Exception):
    """Custom exception for wallet sync errors with error codes"""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(f"{error_code}: {message}")


class WalletSyncManager:
    """
    Robust Wallet Synchronization Manager.
    
    Handles all 13 root causes of "Unable to sync wallet with trading engine":
    1. Wallet loaded after trading engine initialization
    2. Missing PRIVATE_KEY environment variable
    3. Incorrect private key format
    4. RPC connection failure
    5. Wallet balance fetch failure
    6. Phantom wallet UI conflicting with backend wallet
    7. Test mode incorrectly blocking wallet initialization
    8. Trading engine starting before wallet sync
    9. Wallet not passed to trading engine
    10. RPC timeout
    11. Wallet public key undefined
    12. Connection not confirmed
    13. Wallet adapter mismatch
    
    MANDATORY INITIALIZATION ORDER:
    1. Load environment variables
    2. Initialize RPC connection
    3. Load wallet keypair
    4. Validate wallet structure
    5. Verify wallet public key
    6. Fetch wallet balance
    7. Initialize trading engine
    8. Sync wallet with trading engine
    9. Start auto trading
    """
    
    def __init__(self):
        self.sync_in_progress = False
        self.last_successful_sync = None
        self.initialization_complete = False
        self.trading_engine_ready = False
        self.diagnostics = []
    
    def _log_diagnostic(self, event: str, status: str, details: str = None):
        """Log diagnostic event for debugging"""
        entry = {
            "event": event,
            "status": status,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.diagnostics.append(entry)
        if len(self.diagnostics) > 100:
            self.diagnostics = self.diagnostics[-100:]
        
        log_msg = f"{event}: {status}"
        if details:
            log_msg += f" - {details}"
        
        if status == "SUCCESS":
            logger.info(log_msg)
        elif status == "WARNING":
            logger.warning(log_msg)
        else:
            logger.error(log_msg)
    
    async def full_initialization_sequence(self, address: str = None, wallet_type: str = "browser") -> dict:
        """
        Execute full initialization sequence in mandatory order.
        This is the primary entry point for wallet sync.
        
        Args:
            address: Wallet public address (from browser wallet or server keypair)
            wallet_type: "browser" (Phantom/Solflare), "server" (keypair), or "test"
        
        Returns:
            dict with success status and details
        """
        global wallet_state
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("    WALLET SYNC PROCESS - DETAILED DEBUG LOG")
        logger.info("=" * 60)
        logger.info(f"Input Address: {address if address else 'None'}")
        logger.info(f"Wallet Type: {wallet_type}")
        logger.info("=" * 60)
        
        self.diagnostics = []
        results = {
            "success": False,
            "steps_completed": [],
            "steps_failed": [],
            "error": None,
            "wallet_synced": False,
            "trading_engine_ready": False
        }
        
        current_step = 0
        
        try:
            # ============ STEP 1: Environment Variables ============
            current_step = 1
            logger.info("")
            logger.info(f"STEP {current_step}: Checking environment variables...")
            self._log_diagnostic("ENV_CHECK", "STARTED")
            
            env_result = await self._check_environment_variables()
            logger.info(f"   ENV_CHECK result: {env_result}")
            
            if not env_result["success"]:
                logger.error(f"WALLET SYNC FAILED at step {current_step}: {env_result['error']}")
                raise WalletSyncError(env_result["error"], "ENV_VARIABLE_MISSING")
            
            results["steps_completed"].append("ENV_CHECK")
            self._log_diagnostic("ENV_CHECK", "SUCCESS")
            logger.info(f"   ✅ STEP {current_step} OK: Environment variables verified")
            
            # ============ STEP 2: RPC Connection ============
            current_step = 2
            logger.info("")
            logger.info(f"STEP {current_step}: Testing RPC connection...")
            self._log_diagnostic("RPC_INIT", "STARTED")
            
            rpc_result = await self._initialize_rpc_connection()
            logger.info(f"   RPC_INIT result: connected={rpc_result.get('connected')}, endpoint={rpc_result.get('endpoint', 'None')[:50] if rpc_result.get('endpoint') else 'None'}")
            
            if not rpc_result["connected"]:
                logger.error(f"WALLET SYNC FAILED at step {current_step}: {rpc_result.get('error', 'RPC connection failed')}")
                raise WalletSyncError(rpc_result.get("error", "RPC connection failed"), "RPC_CONNECTION_FAILED")
            
            results["steps_completed"].append("RPC_INIT")
            results["rpc_endpoint"] = rpc_result["endpoint"]
            self._log_diagnostic("RPC_CONNECTED", "SUCCESS", rpc_result["endpoint"][:40])
            logger.info(f"   ✅ STEP {current_step} OK: RPC connected to {rpc_result['endpoint'][:40]}...")
            
            # ============ STEP 3: Wallet Address Loading ============
            current_step = 3
            logger.info("")
            logger.info(f"STEP {current_step}: Loading wallet address...")
            
            if not address:
                logger.info("   No address provided, checking for server keypair...")
                private_key = os.environ.get("PRIVATE_KEY") or os.environ.get("SOLANA_PRIVATE_KEY")
                
                if private_key:
                    logger.info("   Found private key in environment, loading keypair...")
                    self._log_diagnostic("KEYPAIR_LOAD", "STARTED")
                    keypair_result = await self._load_server_keypair(private_key)
                    logger.info(f"   KEYPAIR_LOAD result: {keypair_result}")
                    
                    if not keypair_result["success"]:
                        logger.error(f"WALLET SYNC FAILED at step {current_step}: {keypair_result['error']}")
                        raise WalletSyncError(keypair_result["error"], "INVALID_PRIVATE_KEY_FORMAT")
                    
                    address = keypair_result["address"]
                    wallet_type = "server"
                    results["steps_completed"].append("KEYPAIR_LOAD")
                    self._log_diagnostic("WALLET_LOADED", "SUCCESS", f"Server keypair: {address[:12]}...")
                    logger.info(f"   ✅ STEP {current_step} OK: Server keypair loaded, address: {address}")
                else:
                    logger.info("   No private key found - entering test mode")
                    self._log_diagnostic("WALLET_LOAD", "WARNING", "No wallet address - using test mode")
                    wallet_state["sync_status"] = "test_mode"
                    results["steps_completed"].append("TEST_MODE_INIT")
                    results["success"] = True
                    results["test_mode"] = True
                    results["message"] = "Test mode active - no wallet connected"
                    logger.info(f"   ✅ STEP {current_step} OK: Test mode activated")
                    return results
            else:
                logger.info(f"   Address provided: {address}")
                logger.info(f"   ✅ STEP {current_step} OK: Wallet address loaded")
            
            # ============ STEP 4: Validate Wallet Structure ============
            current_step = 4
            logger.info("")
            logger.info(f"STEP {current_step}: Validating wallet address structure...")
            logger.info(f"   Address to validate: {address}")
            self._log_diagnostic("WALLET_VALIDATE", "STARTED")
            
            validation_result = await self._validate_wallet_structure(address)
            logger.info(f"   WALLET_VALIDATE result: {validation_result}")
            
            if not validation_result["valid"]:
                logger.error(f"WALLET SYNC FAILED at step {current_step}: {validation_result['error']}")
                raise WalletSyncError(validation_result["error"], "WALLET_NOT_LOADED")
            
            results["steps_completed"].append("WALLET_VALIDATE")
            self._log_diagnostic("WALLET_VALIDATION_SUCCESS", "SUCCESS")
            logger.info(f"   ✅ STEP {current_step} OK: Wallet address structure valid")
            
            # ============ STEP 5: Verify Public Key ============
            current_step = 5
            logger.info("")
            logger.info(f"STEP {current_step}: Verifying public key format...")
            self._log_diagnostic("PUBKEY_VERIFY", "STARTED")
            
            pubkey_result = await self._verify_public_key(address)
            logger.info(f"   PUBKEY_VERIFY result: {pubkey_result}")
            
            if not pubkey_result["valid"]:
                logger.error(f"WALLET SYNC FAILED at step {current_step}: {pubkey_result['error']}")
                raise WalletSyncError(pubkey_result["error"], "INVALID_WALLET_PUBLIC_KEY")
            
            results["steps_completed"].append("PUBKEY_VERIFY")
            wallet_state["public_key_valid"] = True
            self._log_diagnostic("PUBKEY_VERIFIED", "SUCCESS")
            logger.info(f"   ✅ STEP {current_step} OK: Public key format verified")
            
            # ============ STEP 6: Check Wallet Adapter Conflicts ============
            current_step = 6
            logger.info("")
            logger.info(f"STEP {current_step}: Checking wallet adapter conflicts...")
            self._log_diagnostic("ADAPTER_CHECK", "STARTED")
            
            adapter_result = await self._check_wallet_adapter_conflict(wallet_type)
            logger.info(f"   ADAPTER_CHECK result: {adapter_result}")
            
            if adapter_result["conflict"]:
                logger.warning(f"   ⚠️ Wallet adapter conflict detected: {adapter_result['details']}")
                self._log_diagnostic("WALLET_ADAPTER_CONFLICT", "WARNING", adapter_result["details"])
                wallet_state["adapter_conflict"] = True
            else:
                results["steps_completed"].append("ADAPTER_CHECK")
                self._log_diagnostic("ADAPTER_CHECK", "SUCCESS", f"Type: {wallet_type}")
            logger.info(f"   ✅ STEP {current_step} OK: Adapter check complete")
            
            # ============ STEP 7: Fetch Wallet Balance ============
            current_step = 7
            logger.info("")
            logger.info(f"STEP {current_step}: Fetching wallet balance...")
            logger.info(f"   Calling _fetch_balance_with_retry for address: {address}")
            self._log_diagnostic("BALANCE_FETCH", "STARTED")
            
            balance_result = await self._fetch_balance_with_retry(address)
            logger.info(f"   BALANCE_FETCH result: {balance_result}")
            
            if not balance_result["success"]:
                logger.error(f"WALLET SYNC FAILED at step {current_step}: {balance_result.get('error', 'Balance fetch failed')}")
                raise WalletSyncError(balance_result.get("error", "Balance fetch failed"), "BALANCE_FETCH_FAILED")
            
            balance_sol = balance_result["balance"]
            results["steps_completed"].append("BALANCE_FETCH")
            results["balance"] = balance_sol
            self._log_diagnostic("WALLET_BALANCE_FETCHED", "SUCCESS", f"{balance_sol:.6f} SOL")
            logger.info(f"   ✅ STEP {current_step} OK: Balance fetched = {balance_sol:.6f} SOL")
            
            # Check minimum balance
            if balance_sol < WALLET_SYNC_CONFIG["min_balance_sol"]:
                logger.warning(f"   ⚠️ LOW BALANCE WARNING: {balance_sol:.6f} SOL < {WALLET_SYNC_CONFIG['min_balance_sol']} minimum")
                self._log_diagnostic("LOW_WALLET_BALANCE", "WARNING", 
                    f"{balance_sol:.6f} SOL < {WALLET_SYNC_CONFIG['min_balance_sol']} minimum")
                activity_feed.add_event("WARNING", "WALLET", {
                    "message": f"⚠️ Low balance: {balance_sol:.6f} SOL"
                })
            
            # ============ STEP 8: Initialize Trading Engine ============
            current_step = 8
            logger.info("")
            logger.info(f"STEP {current_step}: Initializing trading engine...")
            self._log_diagnostic("ENGINE_INIT", "STARTED")
            
            engine_result = await self._initialize_trading_engine(address, balance_sol)
            logger.info(f"   ENGINE_INIT result: {engine_result}")
            
            if not engine_result["success"]:
                logger.error(f"WALLET SYNC FAILED at step {current_step}: {engine_result.get('error', 'Engine init failed')}")
                raise WalletSyncError(engine_result.get("error", "Engine init failed"), "TRADING_ENGINE_INIT_FAILED")
            
            results["steps_completed"].append("ENGINE_INIT")
            self._log_diagnostic("TRADING_ENGINE_INITIALIZED", "SUCCESS")
            logger.info(f"   ✅ STEP {current_step} OK: Trading engine initialized")
            
            # ============ STEP 9: Sync Wallet with Engine ============
            current_step = 9
            logger.info("")
            logger.info(f"STEP {current_step}: Syncing wallet with trading engine...")
            self._log_diagnostic("WALLET_SYNC", "STARTED")
            
            sync_result = await self._sync_wallet_to_engine(address, balance_sol, wallet_type)
            logger.info(f"   WALLET_SYNC result: {sync_result}")
            
            if not sync_result["success"]:
                logger.error(f"WALLET SYNC FAILED at step {current_step}: {sync_result.get('error', 'Sync failed')}")
                raise WalletSyncError(sync_result.get("error", "Sync failed"), "WALLET_SYNC_FAILED")
            
            results["steps_completed"].append("WALLET_SYNC")
            self._log_diagnostic("WALLET_SYNC_SUCCESS", "SUCCESS", f"{address[:12]}... synced")
            logger.info(f"   ✅ STEP {current_step} OK: Wallet synced with engine")
            
            # ============ ALL STEPS COMPLETE ============
            self.initialization_complete = True
            self.trading_engine_ready = True
            self.last_successful_sync = datetime.now(timezone.utc)
            
            results["success"] = True
            results["wallet_synced"] = True
            results["trading_engine_ready"] = True
            results["address"] = address
            results["wallet_type"] = wallet_type
            results["synced_at"] = datetime.now(timezone.utc).isoformat()
            results["message"] = "Wallet successfully synced with trading engine"
            
            # Log final success summary
            logger.info("")
            logger.info("=" * 60)
            logger.info("    WALLET SYNC COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            logger.info(f"   Address: {address}")
            logger.info(f"   Balance: {balance_sol:.6f} SOL")
            logger.info(f"   Type: {wallet_type}")
            logger.info(f"   Steps completed: {results['steps_completed']}")
            logger.info("   Trading Engine: READY")
            logger.info("=" * 60)
            logger.info("")
            
            activity_feed.add_event("INFO", "WALLET", {
                "message": f"✅ Full sync complete: {balance_sol:.6f} SOL"
            })
            
            return results
            
        except WalletSyncError as e:
            results["steps_failed"].append(e.error_code)
            results["error"] = e.message
            results["error_code"] = e.error_code
            self._log_diagnostic(e.error_code, "FAILED", e.message)
            
            # Log failure summary
            logger.error("")
            logger.error("=" * 60)
            logger.error(f"    WALLET SYNC FAILED AT STEP {current_step}")
            logger.error("=" * 60)
            logger.error(f"   Error Code: {e.error_code}")
            logger.error(f"   Error Message: {e.message}")
            logger.error(f"   Steps completed: {results['steps_completed']}")
            logger.error(f"   Steps failed: {results['steps_failed']}")
            logger.error("=" * 60)
            logger.error("")
            
            activity_feed.add_event("ERROR", "WALLET", {
                "message": f"❌ Sync failed at step {current_step}: {e.error_code}"
            })
            
            wallet_state["sync_status"] = "error"
            wallet_state["sync_error"] = e.message
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            results["error_code"] = "UNKNOWN_ERROR"
            self._log_diagnostic("WALLET_SYNC_FAILED", "FAILED", str(e))
            
            # Log unexpected error
            logger.error("")
            logger.error("=" * 60)
            logger.error(f"    WALLET SYNC FAILED - UNEXPECTED ERROR AT STEP {current_step}")
            logger.error("=" * 60)
            logger.error(f"   Exception: {type(e).__name__}")
            logger.error(f"   Message: {str(e)}")
            logger.error(f"   Steps completed: {results['steps_completed']}")
            logger.error("=" * 60)
            logger.error("")
            
            wallet_state["sync_status"] = "error"
            wallet_state["sync_error"] = str(e)
            
            return results
    
    async def sync_wallet_with_engine(self, address: str, force: bool = False) -> dict:
        """
        Simplified sync method - calls full initialization sequence.
        Maintains backward compatibility with existing API.
        """
        if self.sync_in_progress and not force:
            return {
                "success": False,
                "error": "Sync already in progress",
                "status": "syncing"
            }
        
        self.sync_in_progress = True
        
        try:
            result = await self.full_initialization_sequence(address, "browser")
            
            if result["success"]:
                return {
                    "success": True,
                    "address": result.get("address"),
                    "balance": result.get("balance", 0),
                    "status": "synced",
                    "rpc_endpoint": result.get("rpc_endpoint"),
                    "synced_at": result.get("synced_at"),
                    "message": result.get("message", "Wallet synced")
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "error_code": result.get("error_code", "UNKNOWN"),
                    "status": "error",
                    "message": "Unable to sync wallet with trading engine"
                }
        finally:
            self.sync_in_progress = False
    
    async def _check_environment_variables(self) -> dict:
        """Check required environment variables"""
        missing_required = []
        for var in REQUIRED_ENV_VARS["required"]:
            if not os.environ.get(var):
                missing_required.append(var)
        
        if missing_required:
            return {
                "success": False,
                "error": f"Missing required env vars: {', '.join(missing_required)}"
            }
        
        # Check optional vars and log warnings
        for var in REQUIRED_ENV_VARS["optional"]:
            if not os.environ.get(var):
                logger.info(f"Optional env var not set: {var}")
        
        return {"success": True}
    
    async def _initialize_rpc_connection(self) -> dict:
        """Initialize RPC with automatic failover"""
        global rpc_state
        
        # First try to get working RPC
        await get_working_rpc()
        
        if rpc_state.get("connected"):
            return {
                "connected": True,
                "endpoint": rpc_state["current_endpoint"]
            }
        
        # Failover: try all endpoints
        for i, endpoint in enumerate(RPC_ENDPOINTS):
            try:
                result = await test_rpc_endpoint(endpoint, WALLET_SYNC_CONFIG["rpc_timeout_seconds"])
                if result.get("success"):
                    rpc_state["connected"] = True
                    rpc_state["current_endpoint"] = endpoint
                    rpc_state["current_endpoint_index"] = i
                    rpc_state["latency_ms"] = result.get("latency_ms")
                    rpc_state["last_slot"] = result.get("slot")
                    
                    if i > 0:
                        logger.info(f"RPC_FAILOVER_ACTIVATED: Switched to {endpoint[:30]}...")
                    
                    return {
                        "connected": True,
                        "endpoint": endpoint,
                        "failover": i > 0
                    }
            except Exception as e:
                logger.warning(f"RPC endpoint {endpoint[:30]}... failed: {e}")
                continue
        
        return {
            "connected": False,
            "error": "All RPC endpoints failed - network unavailable"
        }
    
    async def _load_server_keypair(self, private_key: str) -> dict:
        """Load and validate server-side keypair from PRIVATE_KEY env var"""
        try:
            # Try to parse as JSON array
            if private_key.startswith("["):
                key_array = json.loads(private_key)
                if not isinstance(key_array, list) or len(key_array) != 64:
                    return {
                        "success": False,
                        "error": "Private key must be a JSON array of 64 bytes"
                    }
                # In Python we don't actually create a Keypair, 
                # we just validate and derive the public key
                # For now, we just return success if format is valid
                return {
                    "success": True,
                    "address": "ServerWalletAddress",  # Would derive from keypair
                    "keypair_valid": True
                }
            
            # Try to parse as base58
            import re
            if re.match(r'^[1-9A-HJ-NP-Za-km-z]{87,88}$', private_key):
                return {
                    "success": True,
                    "address": "ServerWalletAddress",
                    "keypair_valid": True
                }
            
            return {
                "success": False,
                "error": "Invalid private key format - must be JSON array or base58"
            }
            
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Invalid private key JSON format"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load keypair: {str(e)}"
            }
    
    async def _validate_wallet_structure(self, address: str) -> dict:
        """Validate wallet address structure"""
        if not address:
            return {"valid": False, "error": "No wallet address provided"}
        
        if not isinstance(address, str):
            return {"valid": False, "error": "Wallet address must be a string"}
        
        # Solana addresses are 32-44 characters base58
        if len(address) < 32 or len(address) > 44:
            return {"valid": False, "error": f"Invalid address length: {len(address)}"}
        
        return {"valid": True}
    
    async def _verify_public_key(self, address: str) -> dict:
        """Verify public key is valid base58 Solana address"""
        import re
        base58_pattern = re.compile(r'^[1-9A-HJ-NP-Za-km-z]+$')
        
        if not base58_pattern.match(address):
            return {
                "valid": False,
                "error": "Invalid base58 characters in address"
            }
        
        return {"valid": True}
    
    async def _check_wallet_adapter_conflict(self, wallet_type: str) -> dict:
        """Check for wallet adapter conflicts between UI and backend"""
        global wallet_state
        
        # If server wallet is being used but UI has a different wallet connected
        if wallet_type == "server" and wallet_state.get("wallet_type") == "browser":
            return {
                "conflict": True,
                "details": "Server wallet conflicts with connected browser wallet"
            }
        
        # If switching wallet types
        if wallet_state.get("wallet_type") and wallet_state["wallet_type"] != wallet_type:
            logger.info(f"Wallet type change: {wallet_state['wallet_type']} -> {wallet_type}")
        
        wallet_state["wallet_type"] = wallet_type
        return {"conflict": False}
    
    async def _fetch_balance_with_retry(self, address: str) -> dict:
        """
        Fetch wallet balance with retry logic.
        Uses native Solana client for reliable balance fetching.
        """
        global wallet_state
        
        max_retries = WALLET_SYNC_CONFIG["max_retries"]
        retry_delay = WALLET_SYNC_CONFIG["retry_delay_seconds"]
        
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            wallet_state["retry_count"] = attempt
            
            try:
                logger.info(f"Balance fetch attempt {attempt}/{max_retries} for {address[:12]}...")
                
                # Try native Solana client first (most reliable)
                if solana_client.initialized or await solana_client.initialize():
                    native_result = await solana_client.get_balance(address)
                    if native_result.get("success"):
                        sol_balance = native_result["balance_sol"]
                        lamports = native_result["balance_lamports"]
                        logger.info(f"✅ Wallet balance fetched successfully: {sol_balance:.6f} SOL ({lamports:,} lamports)")
                        return {
                            "success": True,
                            "balance": sol_balance,
                            "lamports": lamports,
                            "attempts": attempt,
                            "method": "native_client"
                        }
                
                # Fallback to httpx RPC call
                result = await make_rpc_call(
                    "getBalance",
                    [address, {"commitment": "confirmed"}]
                )
                
                # Check for valid RPC response
                if result and result.get("result") is not None:
                    # Handle both direct value and nested structure
                    result_data = result["result"]
                    if isinstance(result_data, dict):
                        lamports = result_data.get("value", 0)
                    else:
                        lamports = result_data
                    
                    sol_balance = lamports / 1e9
                    logger.info(f"✅ Wallet balance fetched successfully: {sol_balance:.6f} SOL ({lamports:,} lamports)")
                    return {
                        "success": True,
                        "balance": sol_balance,
                        "lamports": lamports,
                        "attempts": attempt,
                        "method": "rpc_call"
                    }
                
                # Check if result indicates failure
                if result and result.get("success") == False:
                    last_error = result.get("error", "RPC returned failure")
                else:
                    last_error = "Invalid RPC response structure"
                
                logger.warning(f"Balance fetch failed (attempt {attempt}): {last_error}")
                
            except asyncio.TimeoutError:
                last_error = "RPC timeout"
                logger.warning(f"Balance fetch timeout (attempt {attempt})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Balance fetch exception (attempt {attempt}): {e}")
            
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
        
        logger.error(f"❌ Balance fetch failed after {max_retries} attempts: {last_error}")
        return {
            "success": False,
            "error": f"Balance fetch failed after {max_retries} attempts: {last_error}",
            "attempts": max_retries
        }
    
    async def _initialize_trading_engine(self, address: str, balance: float) -> dict:
        """Initialize trading engine with wallet data"""
        global wallet_state
        
        try:
            # Update wallet state for trading engine
            wallet_state.update({
                "address": address,
                "balance_sol": balance,
                "last_update": datetime.now(timezone.utc).isoformat()
            })
            
            self.trading_engine_ready = True
            return {"success": True}
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to initialize trading engine: {str(e)}"
            }
    
    async def _sync_wallet_to_engine(self, address: str, balance: float, wallet_type: str) -> dict:
        """Final sync step - ensure wallet is connected to trading engine"""
        global wallet_state
        
        try:
            wallet_state.update({
                "address": address,
                "balance_sol": balance,
                "sync_status": "synced",
                "sync_error": None,
                "wallet_type": wallet_type,
                "validation_passed": True,
                "public_key_valid": True
            })
            
            return {"success": True}
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Wallet sync failed: {str(e)}"
            }
    
    def get_sync_status(self) -> dict:
        """Get comprehensive wallet sync status"""
        return {
            "address": wallet_state.get("address"),
            "balance_sol": wallet_state.get("balance_sol", 0.0),
            "sync_status": wallet_state.get("sync_status", "disconnected"),
            "sync_error": wallet_state.get("sync_error"),
            "validation_passed": wallet_state.get("validation_passed", False),
            "public_key_valid": wallet_state.get("public_key_valid", False),
            "wallet_type": wallet_state.get("wallet_type"),
            "adapter_conflict": wallet_state.get("adapter_conflict", False),
            "last_update": wallet_state.get("last_update"),
            "retry_count": wallet_state.get("retry_count", 0),
            "synced": wallet_state.get("sync_status") == "synced",
            "trading_engine_ready": self.trading_engine_ready,
            "initialization_complete": self.initialization_complete
        }
    
    def get_diagnostics(self) -> list:
        """Get diagnostic log for debugging"""
        return self.diagnostics
    
    def can_start_auto_trading(self) -> tuple:
        """
        Check if auto trading can start.
        Returns (can_start, reason)
        """
        if not self.initialization_complete:
            return False, "Wallet initialization not complete"
        
        if wallet_state.get("sync_status") != "synced":
            return False, f"Wallet not synced: {wallet_state.get('sync_error', 'unknown')}"
        
        if wallet_state.get("adapter_conflict"):
            return False, "Wallet adapter conflict detected"
        
        if not self.trading_engine_ready:
            return False, "Trading engine not ready"
        
        return True, "Ready to start"


# Initialize wallet sync manager
wallet_sync_manager = WalletSyncManager()

class RPCStatus(BaseModel):
    connected: bool
    endpoint: Optional[str] = None
    latency_ms: Optional[float] = None
    last_check: Optional[str] = None
    last_slot: Optional[int] = None
    consecutive_failures: int = 0
    success_rate: float = 100.0

async def test_network_connectivity() -> dict:
    """
    Test if server can make outbound requests.
    This diagnoses network-level issues before RPC testing.
    """
    global network_diagnostic
    
    test_urls = [
        "https://rpc.ankr.com/solana",
        "https://api.mainnet-beta.solana.com",
        "https://1.1.1.1"  # Cloudflare DNS as simple connectivity test
    ]
    
    logger.info("🔍 NETWORK_DIAGNOSTIC: Testing outbound connectivity...")
    
    for url in test_urls:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Just try to connect, don't need valid response
                response = await client.get(url if "1.1.1.1" in url else url, 
                                           follow_redirects=True)
                
                network_diagnostic["outbound_available"] = True
                network_diagnostic["last_check"] = datetime.now(timezone.utc).isoformat()
                network_diagnostic["error"] = None
                
                logger.info(f"✅ NETWORK_AVAILABLE: Outbound requests working (tested {url[:30]}...)")
                return {"success": True, "message": "Network available"}
                
        except Exception as e:
            logger.warning(f"⚠️ Network test failed for {url[:30]}...: {e}")
            continue
    
    # All tests failed
    network_diagnostic["outbound_available"] = False
    network_diagnostic["last_check"] = datetime.now(timezone.utc).isoformat()
    network_diagnostic["error"] = "All outbound requests failed"
    
    logger.error("❌ NETWORK_BLOCKED: Server cannot make outbound requests")
    return {"success": False, "error": "NETWORK_BLOCKED"}


async def test_rpc_health(endpoint: str, timeout: int = 15) -> dict:
    """
    Test RPC endpoint using getHealth method.
    More reliable than getSlot for health checking.
    """
    try:
        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            start_time = datetime.now()
            
            # First try getHealth
            response = await client.post(
                endpoint,
                json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"},
                headers={"Content-Type": "application/json"}
            )
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data and data["result"] == "ok":
                    return {
                        "success": True,
                        "healthy": True,
                        "latency_ms": round(latency, 1),
                        "endpoint": endpoint
                    }
                elif "error" in data:
                    # Some RPCs don't support getHealth, fall back to getSlot
                    return await test_rpc_endpoint(endpoint, timeout)
            
            # Rate limited
            if response.status_code == 429:
                return {
                    "success": False, 
                    "error": "RPC_RATE_LIMITED",
                    "rate_limited": True
                }
            
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except httpx.TimeoutException:
        return {"success": False, "error": "RPC_TIMEOUT"}
    except httpx.ConnectError:
        return {"success": False, "error": "RPC_CONNECTION_REFUSED"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def test_rpc_endpoint(endpoint: str, timeout: int = 15) -> dict:
    """Test a single RPC endpoint using getSlot and return status"""
    global rpc_state
    
    try:
        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            start_time = datetime.now()
            response = await client.post(
                endpoint,
                json={"jsonrpc": "2.0", "id": 1, "method": "getSlot"},
                headers={"Content-Type": "application/json"}
            )
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            # Handle rate limiting
            if response.status_code == 429:
                logger.warning(f"⚠️ RPC_RATE_LIMITED: {endpoint[:30]}...")
                # Set backoff time
                rpc_state["rate_limited_until"] = (
                    datetime.now(timezone.utc) + 
                    timedelta(seconds=RPC_CONFIG["rate_limit_backoff"])
                ).isoformat()
                return {
                    "success": False, 
                    "error": "RPC_RATE_LIMITED",
                    "rate_limited": True
                }
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    # Update provider status
                    rpc_state["provider_status"][endpoint[:30]] = {
                        "healthy": True,
                        "latency_ms": round(latency, 1),
                        "last_check": datetime.now(timezone.utc).isoformat()
                    }
                    return {
                        "success": True,
                        "latency_ms": round(latency, 1),
                        "slot": data["result"],
                        "endpoint": endpoint
                    }
                elif "error" in data:
                    error_msg = data["error"].get("message", "RPC error")
                    rpc_state["provider_status"][endpoint[:30]] = {
                        "healthy": False,
                        "error": error_msg,
                        "last_check": datetime.now(timezone.utc).isoformat()
                    }
                    return {"success": False, "error": error_msg}
            
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except httpx.TimeoutException:
        logger.warning(f"⚠️ RPC_TIMEOUT: {endpoint[:30]}... (>{timeout}s)")
        rpc_state["provider_status"][endpoint[:30]] = {
            "healthy": False,
            "error": "TIMEOUT",
            "last_check": datetime.now(timezone.utc).isoformat()
        }
        return {"success": False, "error": "RPC_TIMEOUT"}
    except httpx.ConnectError as e:
        logger.warning(f"⚠️ RPC_CONNECTION_REFUSED: {endpoint[:30]}...")
        return {"success": False, "error": "RPC_CONNECTION_REFUSED"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_working_rpc() -> dict:
    """
    Find a working RPC endpoint with automatic failover.
    
    Process:
    1. Test network connectivity first
    2. Try each RPC endpoint in order
    3. Select first working endpoint
    4. Log RPC_PROVIDER_SELECTED or RPC_ALL_PROVIDERS_FAILED
    """
    global rpc_state, network_diagnostic
    
    logger.info("🔍 RPC_TEST: Finding working RPC provider...")
    
    # Step 1: Test network connectivity first
    if not network_diagnostic.get("outbound_available"):
        network_result = await test_network_connectivity()
        if not network_result["success"]:
            logger.error("❌ RPC_ALL_PROVIDERS_FAILED: Network unavailable")
            rpc_state["connected"] = False
            rpc_state["network_available"] = False
            return {
                "success": False, 
                "error": "NETWORK_UNAVAILABLE",
                "message": "Failed to sync wallet. Network unavailable."
            }
    
    rpc_state["network_available"] = True
    
    # Step 2: Try endpoints in order, starting from current
    tested_count = 0
    for i in range(len(RPC_CONFIG["endpoints"])):
        idx = (rpc_state["current_endpoint_index"] + i) % len(RPC_CONFIG["endpoints"])
        endpoint = RPC_CONFIG["endpoints"][idx]
        
        tested_count += 1
        logger.info(f"   Testing RPC {tested_count}/{len(RPC_CONFIG['endpoints'])}: {endpoint[:40]}...")
        
        # Check if rate limited
        if rpc_state.get("rate_limited_until"):
            try:
                limit_time = datetime.fromisoformat(rpc_state["rate_limited_until"].replace('Z', '+00:00'))
                if datetime.now(timezone.utc) < limit_time:
                    logger.info(f"   ⏳ Skipping (rate limited until {rpc_state['rate_limited_until']})")
                    continue
            except:
                pass
        
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
            rpc_state["rate_limited_until"] = None
            
            logger.info(f"✅ RPC_PROVIDER_SELECTED: {endpoint[:40]}...")
            logger.info(f"   RPC_CONNECTION_SUCCESS | Latency: {result['latency_ms']}ms | Slot: {result['slot']}")
            return result
        else:
            rpc_state["failed_requests"] += 1
            error_type = result.get("error", "Unknown")
            
            # Log specific error type
            if "RATE_LIMITED" in str(error_type):
                logger.warning(f"   ⚠️ Provider {idx+1} rate limited - trying next")
            elif "TIMEOUT" in str(error_type):
                logger.warning(f"   ⚠️ Provider {idx+1} timeout - trying next")
            else:
                logger.warning(f"   ⚠️ Provider {idx+1} failed: {error_type}")
    
    # All endpoints failed
    rpc_state["connected"] = False
    rpc_state["consecutive_failures"] += 1
    rpc_state["last_check"] = datetime.now(timezone.utc).isoformat()
    
    logger.error("=" * 50)
    logger.error("❌ RPC_ALL_PROVIDERS_FAILED")
    logger.error(f"   Tested {tested_count} providers, all failed")
    logger.error("   Error: NETWORK_UNAVAILABLE")
    logger.error("=" * 50)
    
    return {
        "success": False, 
        "error": "RPC_ALL_PROVIDERS_FAILED",
        "message": "Failed to sync wallet. Network unavailable."
    }

async def make_rpc_call(method: str, params: list = None, retries: int = 3) -> dict:
    """
    Make a Solana JSON-RPC call with automatic failover.
    
    Returns the raw Solana RPC response format:
    {
        "jsonrpc": "2.0",
        "result": {...},
        "id": 1
    }
    
    Also includes "success": True for backward compatibility.
    """
    global rpc_state
    
    # RPC endpoints with failover
    rpc_endpoints = [
        "https://api.mainnet-beta.solana.com",  # Official - most reliable
        "https://rpc.ankr.com/solana",
        "https://solana.public-rpc.com",
        "https://solana-mainnet.rpc.extrnode.com"
    ]
    
    # Use current connected endpoint first if available
    if rpc_state.get("connected") and rpc_state.get("current_endpoint"):
        # Move current endpoint to front
        current = rpc_state["current_endpoint"]
        if current in rpc_endpoints:
            rpc_endpoints.remove(current)
        rpc_endpoints.insert(0, current)
    
    last_error = None
    
    for endpoint in rpc_endpoints:
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": method
                    }
                    if params:
                        payload["params"] = params
                    
                    start_time = datetime.now()
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    latency = (datetime.now() - start_time).total_seconds() * 1000
                    
                    # Track stats
                    rpc_state["total_requests"] = rpc_state.get("total_requests", 0) + 1
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Check for valid result
                        if "result" in data:
                            # Update RPC state on success
                            rpc_state["connected"] = True
                            rpc_state["current_endpoint"] = endpoint
                            rpc_state["latency_ms"] = round(latency, 1)
                            rpc_state["consecutive_failures"] = 0
                            rpc_state["last_check"] = datetime.now(timezone.utc).isoformat()
                            
                            logger.info(f"✅ RPC call successful: {method} ({latency:.0f}ms)")
                            
                            # Return with both raw format and success flag
                            return {
                                "success": True,
                                "result": data["result"],
                                "jsonrpc": data.get("jsonrpc"),
                                "id": data.get("id"),
                                "latency_ms": latency
                            }
                        
                        # Handle RPC error response
                        if "error" in data:
                            error_msg = data["error"].get("message", str(data["error"]))
                            logger.warning(f"RPC error from {endpoint[:30]}...: {error_msg}")
                            last_error = error_msg
                            break  # Try next endpoint
                    
                    elif response.status_code == 429:
                        logger.warning(f"Rate limited at {endpoint[:30]}... (attempt {attempt+1})")
                        last_error = "Rate limited"
                        await asyncio.sleep(2)  # Wait before retry
                        continue
                    
                    else:
                        last_error = f"HTTP {response.status_code}"
                        logger.warning(f"HTTP error at {endpoint[:30]}...: {response.status_code}")
                        break  # Try next endpoint
                        
            except httpx.TimeoutException:
                last_error = "Timeout"
                logger.warning(f"Timeout at {endpoint[:30]}... (attempt {attempt+1})")
            except httpx.ConnectError:
                last_error = "Connection refused"
                logger.warning(f"Connection refused at {endpoint[:30]}...")
                break  # Try next endpoint immediately
            except Exception as e:
                last_error = str(e)
                logger.warning(f"RPC exception at {endpoint[:30]}...: {e}")
            
            if attempt < retries - 1:
                await asyncio.sleep(1)
        
        # If we get here, this endpoint failed - try next
    
    # All endpoints failed
    rpc_state["connected"] = False
    rpc_state["consecutive_failures"] = rpc_state.get("consecutive_failures", 0) + 1
    rpc_state["failed_requests"] = rpc_state.get("failed_requests", 0) + 1
    
    logger.error(f"❌ RPC call failed: {method} - {last_error}")
    
    return {
        "success": False,
        "error": last_error or "Network unavailable",
        "result": None
    }

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
    """Start RPC health monitor and initialize wallet manager on app startup"""
    global rpc_monitor_task, auto_trading_state, auto_trading_task
    
    logger.info("=" * 60)
    logger.info("🚀 TRADING BOT STARTUP SEQUENCE")
    logger.info("=" * 60)
    
    # STEP 1: Reset auto trading state on startup to prevent "already running" error
    auto_trading_state["is_running"] = False
    auto_trading_state["is_paused"] = False
    auto_trading_state["pause_reason"] = None
    auto_trading_task = None
    logger.info("✅ AUTO_TRADING_STATE_RESET")
    
    # STEP 2: Initialize WalletSyncManager
    logger.info("WALLET_MANAGER_INITIALIZED")
    logger.info(f"   - Max retries: {WALLET_SYNC_CONFIG['max_retries']}")
    logger.info(f"   - Min balance: {WALLET_SYNC_CONFIG['min_balance_sol']} SOL")
    
    # STEP 3: Initial RPC connection test
    logger.info("🔌 Initializing RPC connection...")
    await get_working_rpc()
    
    if rpc_state.get("connected"):
        logger.info(f"RPC_CONNECTED: {rpc_state.get('current_endpoint', 'unknown')[:40]}...")
    else:
        logger.warning("⚠️ RPC_CONNECTION_FAILED - will retry on first request")
    
    # STEP 4: Start background RPC monitor
    rpc_monitor_task = asyncio.create_task(rpc_health_monitor())
    logger.info("✅ RPC_HEALTH_MONITOR_STARTED")
    
    # Log startup complete
    logger.info("=" * 60)
    logger.info("✅ TRADING BOT STARTUP COMPLETE")
    logger.info("   - Wallet: Waiting for connection")
    logger.info("   - RPC: " + ("Connected" if rpc_state.get("connected") else "Pending"))
    logger.info("   - Auto-Trading: Stopped (ready to start)")
    logger.info("=" * 60)

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


@api_router.get("/rpc/network-diagnostic")
async def run_network_diagnostic():
    """
    Run comprehensive network diagnostic to identify RPC connection issues.
    
    Checks:
    1. Outbound network connectivity
    2. Each RPC provider status
    3. Rate limiting status
    4. Overall network health
    """
    global network_diagnostic, rpc_state
    
    logger.info("=" * 50)
    logger.info("🔍 NETWORK DIAGNOSTIC STARTED")
    logger.info("=" * 50)
    
    diagnostic_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "network_available": False,
        "rpc_connected": False,
        "providers_tested": 0,
        "providers_working": 0,
        "selected_provider": None,
        "provider_results": [],
        "error": None,
        "recommendation": None
    }
    
    # Step 1: Test network connectivity
    logger.info("Step 1: Testing outbound network connectivity...")
    network_result = await test_network_connectivity()
    diagnostic_result["network_available"] = network_result["success"]
    
    if not network_result["success"]:
        diagnostic_result["error"] = "NETWORK_BLOCKED"
        diagnostic_result["recommendation"] = "Server cannot make outbound requests. Check firewall/proxy settings."
        logger.error("❌ NETWORK_BLOCKED: Cannot proceed with RPC testing")
        return diagnostic_result
    
    logger.info("✅ Network connectivity confirmed")
    
    # Step 2: Test each RPC provider
    logger.info("Step 2: Testing RPC providers...")
    
    for i, endpoint in enumerate(RPC_CONFIG["endpoints"]):
        logger.info(f"   Testing provider {i+1}/{len(RPC_CONFIG['endpoints'])}: {endpoint[:40]}...")
        
        # Test with getHealth first (more reliable)
        result = await test_rpc_health(endpoint, RPC_CONFIG["timeout"])
        
        provider_status = {
            "endpoint": endpoint[:50] + "...",
            "index": i,
            "success": result["success"],
            "latency_ms": result.get("latency_ms"),
            "error": result.get("error"),
            "rate_limited": result.get("rate_limited", False)
        }
        
        diagnostic_result["provider_results"].append(provider_status)
        diagnostic_result["providers_tested"] += 1
        
        if result["success"]:
            diagnostic_result["providers_working"] += 1
            if not diagnostic_result["selected_provider"]:
                diagnostic_result["selected_provider"] = endpoint[:50]
                diagnostic_result["rpc_connected"] = True
                logger.info(f"   ✅ Provider {i+1} working: {result.get('latency_ms')}ms")
        else:
            error_type = result.get("error", "Unknown")
            if "RATE_LIMITED" in str(error_type):
                logger.warning(f"   ⚠️ Provider {i+1} rate limited")
            elif "TIMEOUT" in str(error_type):
                logger.warning(f"   ⚠️ Provider {i+1} timeout (>{RPC_CONFIG['timeout']}s)")
            else:
                logger.warning(f"   ❌ Provider {i+1} failed: {error_type}")
    
    # Step 3: Generate recommendation
    if diagnostic_result["providers_working"] == 0:
        diagnostic_result["error"] = "RPC_ALL_PROVIDERS_FAILED"
        diagnostic_result["recommendation"] = (
            "All RPC providers failed. Possible causes:\n"
            "1. All providers rate limiting - wait and retry\n"
            "2. Network issues - check internet connection\n"
            "3. All providers down - check Solana network status"
        )
        logger.error("❌ RPC_ALL_PROVIDERS_FAILED")
    elif diagnostic_result["providers_working"] < len(RPC_CONFIG["endpoints"]) // 2:
        diagnostic_result["recommendation"] = (
            f"Only {diagnostic_result['providers_working']}/{diagnostic_result['providers_tested']} "
            "providers working. Consider adding more RPC endpoints or using a premium provider."
        )
    else:
        diagnostic_result["recommendation"] = "RPC connection healthy"
    
    logger.info("=" * 50)
    logger.info(f"DIAGNOSTIC COMPLETE: {diagnostic_result['providers_working']}/{diagnostic_result['providers_tested']} providers working")
    logger.info("=" * 50)
    
    return diagnostic_result


@api_router.post("/rpc/force-reconnect")
async def force_rpc_reconnect():
    """Force reconnection to RPC with fresh network diagnostic"""
    global rpc_state, network_diagnostic
    
    # Reset state
    rpc_state["connected"] = False
    rpc_state["consecutive_failures"] = 0
    rpc_state["rate_limited_until"] = None
    network_diagnostic["outbound_available"] = None
    
    logger.info("🔄 Forcing RPC reconnection...")
    
    # Run fresh connection attempt
    result = await get_working_rpc()
    
    return {
        "success": result.get("success", False),
        "connected": rpc_state.get("connected", False),
        "endpoint": rpc_state.get("current_endpoint", "none")[:50] if rpc_state.get("current_endpoint") else None,
        "latency_ms": rpc_state.get("latency_ms"),
        "slot": rpc_state.get("last_slot"),
        "error": result.get("error") if not result.get("success") else None
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
async def sync_wallet(address: str, force: bool = False):
    """
    Sync wallet address and fetch balance - call this when wallet connects.
    This ensures the trading engine has the current wallet balance.
    
    Uses WalletSyncManager with:
    - Wallet validation
    - RPC connection verification with failover
    - Balance fetch with retry logic
    - Activity logging
    
    Args:
        address: Solana wallet address
        force: Force sync even if already syncing
    """
    if not address:
        return {
            "success": False, 
            "error": "No address provided",
            "message": "Unable to sync wallet with trading engine"
        }
    
    # Use the new wallet sync manager
    result = await wallet_sync_manager.sync_wallet_with_engine(address, force=force)
    
    return result


@api_router.post("/wallet/disconnect")
async def disconnect_wallet():
    """Clear wallet state when wallet disconnects"""
    global wallet_state
    
    old_address = wallet_state.get("address")
    wallet_state.update({
        "address": None,
        "balance_sol": 0.0,
        "last_update": None,
        "sync_status": "disconnected",
        "sync_error": None,
        "validation_passed": False,
        "retry_count": 0
    })
    
    if old_address:
        logger.info(f"🔌 Wallet disconnected: {old_address[:8]}...")
        activity_feed.add_event("INFO", "WALLET", {
            "message": f"🔌 Wallet disconnected"
        })
    
    return {"success": True, "message": "Wallet state cleared", "status": "disconnected"}


@api_router.get("/wallet/state")
async def get_wallet_state():
    """Get current wallet state synced with trading engine"""
    return wallet_sync_manager.get_sync_status()


@api_router.get("/wallet/sync-status")
async def get_wallet_sync_status():
    """Get detailed wallet sync status for debugging"""
    return {
        **wallet_sync_manager.get_sync_status(),
        "sync_config": WALLET_SYNC_CONFIG,
        "rpc_connected": rpc_state.get("connected", False),
        "rpc_endpoint": rpc_state.get("current_endpoint", "none")[:30] + "..." if rpc_state.get("current_endpoint") else "none"
    }


@api_router.get("/wallet/diagnostics")
async def get_wallet_diagnostics():
    """Get wallet sync diagnostic log for debugging sync issues"""
    can_trade, reason = wallet_sync_manager.can_start_auto_trading()
    
    return {
        "diagnostics": wallet_sync_manager.get_diagnostics(),
        "current_status": wallet_sync_manager.get_sync_status(),
        "can_start_auto_trading": can_trade,
        "trading_blocked_reason": None if can_trade else reason,
        "initialization_complete": wallet_sync_manager.initialization_complete,
        "trading_engine_ready": wallet_sync_manager.trading_engine_ready,
        "root_cause_checks": {
            "1_wallet_init_order": "OK" if wallet_sync_manager.initialization_complete else "FAILED",
            "2_env_vars": "OK",  # Checked during init
            "3_private_key_format": "N/A (browser wallet mode)",
            "4_rpc_connection": "OK" if rpc_state.get("connected") else "FAILED",
            "5_balance_fetch": "OK" if wallet_state.get("balance_sol", -1) >= 0 else "FAILED",
            "6_phantom_conflict": "OK" if not wallet_state.get("adapter_conflict") else "CONFLICT",
            "7_test_mode": "OK",  # Test mode doesn't block sync
            "8_engine_start_order": "OK" if wallet_sync_manager.trading_engine_ready else "NOT_READY",
            "9_wallet_passed": "OK" if wallet_state.get("address") else "NO_WALLET",
            "10_rpc_timeout": "OK" if rpc_state.get("connected") else "TIMEOUT",
            "11_public_key": "OK" if wallet_state.get("public_key_valid") else "INVALID",
            "12_connection_confirmed": "OK" if rpc_state.get("connected") else "NOT_CONFIRMED",
            "13_adapter_mismatch": "OK" if not wallet_state.get("adapter_conflict") else "MISMATCH"
        }
    }


@api_router.post("/wallet/full-init")
async def full_wallet_initialization(address: str = None, wallet_type: str = "browser"):
    """
    Execute full wallet initialization sequence.
    
    This endpoint runs the complete initialization in mandatory order:
    1. Environment variables check
    2. RPC connection initialization
    3. Wallet keypair/address loading
    4. Wallet structure validation
    5. Public key verification
    6. Adapter conflict check
    7. Balance fetch
    8. Trading engine initialization
    9. Wallet sync
    
    Args:
        address: Wallet public address (optional for server keypair mode)
        wallet_type: "browser", "server", or "test"
    """
    result = await wallet_sync_manager.full_initialization_sequence(address, wallet_type)
    return result


@api_router.get("/wallet/can-trade")
async def check_can_start_trading():
    """Check if auto trading can start based on wallet sync status"""
    can_trade, reason = wallet_sync_manager.can_start_auto_trading()
    
    return {
        "can_start": can_trade,
        "reason": reason,
        "wallet_synced": wallet_state.get("sync_status") == "synced",
        "trading_engine_ready": wallet_sync_manager.trading_engine_ready,
        "initialization_complete": wallet_sync_manager.initialization_complete
    }


@api_router.get("/wallet/status")
async def get_wallet_status():
    """
    Simple wallet status endpoint for frontend polling.
    Returns the current wallet sync state in a simple format.
    
    This is the primary endpoint for frontend to check wallet connection status.
    """
    is_synced = wallet_state.get("sync_status") == "synced"
    
    return {
        "wallet_synced": is_synced,
        "wallet_address": wallet_state.get("address"),
        "balance_sol": wallet_state.get("balance_sol", 0.0) if is_synced else 0.0,
        "sync_status": wallet_state.get("sync_status", "disconnected"),
        "last_update": wallet_state.get("last_update"),
        "trading_engine_ready": wallet_sync_manager.trading_engine_ready,
        "can_trade": is_synced and wallet_sync_manager.trading_engine_ready
    }


# ============== NATIVE SOLANA CLIENT ENDPOINTS ==============

@api_router.post("/solana/init")
async def init_solana_client():
    """Initialize the native Solana client"""
    result = await solana_client.initialize()
    return result


@api_router.get("/solana/status")
async def get_solana_client_status():
    """Get native Solana client status"""
    return {
        "initialized": solana_client.initialized,
        "current_rpc": solana_client.current_rpc[:50] + "..." if solana_client.current_rpc else None,
        "keypair_loaded": solana_client.keypair is not None,
        "pubkey": solana_client.get_pubkey()
    }


@api_router.post("/solana/load-keypair")
async def load_solana_keypair():
    """Load keypair from SOLANA_PRIVATE_KEY environment variable"""
    result = solana_client.load_keypair_from_env()
    return result


@api_router.get("/solana/balance/{address}")
async def get_native_balance(address: str):
    """Get SOL balance using native Solana client"""
    result = await solana_client.get_balance(address)
    return result


@api_router.get("/solana/slot")
async def get_current_slot():
    """Get current slot from Solana network"""
    result = await solana_client.get_slot()
    return result


@api_router.get("/solana/blockhash")
async def get_blockhash():
    """Get recent blockhash for transactions"""
    result = await solana_client.get_recent_blockhash()
    return result


@api_router.get("/solana/tokens/{address}")
async def get_native_token_accounts(address: str):
    """Get SPL token accounts using native client"""
    result = await solana_client.get_token_accounts(address)
    return result


@api_router.post("/solana/switch-rpc")
async def switch_solana_rpc(rpc_url: str):
    """Switch to a different RPC endpoint"""
    result = await solana_client.switch_rpc(rpc_url)
    return result


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
