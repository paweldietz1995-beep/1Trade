from fastapi import FastAPI, APIRouter, HTTPException, Depends
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
from datetime import datetime, timezone
import secrets
import hashlib
import httpx
import asyncio
from decimal import Decimal

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

# ============== MODELS ==============

class AuthRequest(BaseModel):
    pin: str

class AuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str

class TradingSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stake_per_trade: float = 10.0
    max_loss_percent: float = 50.0
    take_profit_percent: float = 100.0
    stop_loss_percent: float = 30.0
    max_parallel_trades: int = 3
    max_daily_trades: int = 10
    paper_mode: bool = True
    auto_mode: bool = False
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TokenRiskAnalysis(BaseModel):
    honeypot_risk: str  # LOW, MEDIUM, HIGH
    rugpull_risk: str
    liquidity_locked: bool
    dev_wallet_percent: float
    top_holder_percent: float
    risk_score: int  # 0-100

class TokenData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    address: str
    name: str
    symbol: str
    price_usd: float
    price_change_24h: float
    market_cap: float
    liquidity: float
    volume_24h: float
    holders: int
    buyers_24h: int
    sellers_24h: int
    buy_sell_ratio: float
    age_hours: float
    risk_analysis: Optional[TokenRiskAnalysis] = None
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Trade(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_address: str
    token_symbol: str
    token_name: str
    trade_type: str  # BUY, SELL
    amount_sol: float
    amount_tokens: float
    price_entry: float
    price_current: float
    price_exit: Optional[float] = None
    take_profit: float
    stop_loss: float
    status: str = "OPEN"  # OPEN, CLOSED, PENDING
    pnl: float = 0.0
    pnl_percent: float = 0.0
    paper_trade: bool = True
    wallet_address: Optional[str] = None
    tx_signature: Optional[str] = None
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None

class TradeCreate(BaseModel):
    token_address: str
    token_symbol: str
    token_name: str
    trade_type: str
    amount_sol: float
    price_entry: float
    take_profit_percent: float
    stop_loss_percent: float
    paper_trade: bool = True
    wallet_address: Optional[str] = None

class PortfolioSummary(BaseModel):
    total_value_sol: float
    total_pnl: float
    total_pnl_percent: float
    open_trades: int
    closed_trades: int
    win_rate: float
    best_trade_pnl: float
    worst_trade_pnl: float

class WalletInfo(BaseModel):
    address: str
    balance_sol: float
    balance_usd: float
    nickname: Optional[str] = None

# ============== HELPER FUNCTIONS ==============

def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()

def generate_token() -> str:
    return secrets.token_urlsafe(32)

async def get_sol_price() -> float:
    """Get current SOL price from CoinGecko"""
    try:
        async with httpx.AsyncClient() as client_http:
            response = await client_http.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "solana", "vs_currencies": "usd"}
            )
            data = response.json()
            return data.get("solana", {}).get("usd", 150.0)
    except Exception as e:
        logger.error(f"Error fetching SOL price: {e}")
        return 150.0

async def fetch_dex_screener_tokens(limit: int = 20) -> List[Dict]:
    """Fetch trending tokens from DEX Screener"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            # DEX Screener Solana pairs endpoint
            response = await client_http.get(
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "pump.fun"}
            )
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])[:limit]
                return pairs
    except Exception as e:
        logger.error(f"Error fetching DEX Screener data: {e}")
    return []

def calculate_risk_score(token_data: Dict) -> TokenRiskAnalysis:
    """Calculate risk analysis for a token"""
    # Simulated risk analysis based on available data
    liquidity = float(token_data.get("liquidity", {}).get("usd", 0) or 0)
    volume = float(token_data.get("volume", {}).get("h24", 0) or 0)
    price_change = float(token_data.get("priceChange", {}).get("h24", 0) or 0)
    
    # Risk calculations
    honeypot_risk = "LOW" if liquidity > 10000 else "MEDIUM" if liquidity > 1000 else "HIGH"
    rugpull_risk = "LOW" if liquidity > 50000 else "MEDIUM" if liquidity > 5000 else "HIGH"
    liquidity_locked = liquidity > 20000
    dev_wallet_percent = 5.0 if liquidity > 10000 else 15.0
    top_holder_percent = 20.0 if volume > 10000 else 40.0
    
    # Overall risk score (0-100, higher = riskier)
    risk_score = 50
    if liquidity < 5000:
        risk_score += 20
    if volume < 1000:
        risk_score += 15
    if abs(price_change) > 50:
        risk_score += 10
    risk_score = min(100, max(0, risk_score))
    
    return TokenRiskAnalysis(
        honeypot_risk=honeypot_risk,
        rugpull_risk=rugpull_risk,
        liquidity_locked=liquidity_locked,
        dev_wallet_percent=dev_wallet_percent,
        top_holder_percent=top_holder_percent,
        risk_score=risk_score
    )

# ============== AUTH ENDPOINTS ==============

@api_router.post("/auth/login", response_model=AuthResponse)
async def login(request: AuthRequest):
    """Simple PIN-based authentication for single user"""
    # Get stored PIN hash or create default
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

# ============== SETTINGS ENDPOINTS ==============

@api_router.get("/settings", response_model=TradingSettings)
async def get_settings():
    """Get current trading settings"""
    settings = await db.settings.find_one({"type": "trading"}, {"_id": 0})
    if not settings:
        default_settings = TradingSettings()
        doc = default_settings.model_dump()
        doc["type"] = "trading"
        doc["updated_at"] = doc["updated_at"].isoformat()
        await db.settings.insert_one(doc)
        return default_settings
    
    if isinstance(settings.get("updated_at"), str):
        settings["updated_at"] = datetime.fromisoformat(settings["updated_at"])
    return TradingSettings(**settings)

@api_router.put("/settings", response_model=TradingSettings)
async def update_settings(settings: TradingSettings):
    """Update trading settings"""
    doc = settings.model_dump()
    doc["type"] = "trading"
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.settings.update_one(
        {"type": "trading"},
        {"$set": doc},
        upsert=True
    )
    return settings

# ============== TOKEN SCANNER ENDPOINTS ==============

@api_router.get("/tokens/scan", response_model=List[TokenData])
async def scan_tokens(limit: int = 20):
    """Scan for new and trending pump.fun tokens"""
    pairs = await fetch_dex_screener_tokens(limit)
    
    tokens = []
    for pair in pairs:
        try:
            base_token = pair.get("baseToken", {})
            price_change = pair.get("priceChange", {})
            volume = pair.get("volume", {})
            liquidity = pair.get("liquidity", {})
            
            # Calculate age in hours
            created_at = pair.get("pairCreatedAt", 0)
            if created_at:
                age_hours = (datetime.now(timezone.utc).timestamp() * 1000 - created_at) / (1000 * 60 * 60)
            else:
                age_hours = 0
            
            # Calculate buy/sell ratio from txns
            txns = pair.get("txns", {}).get("h24", {})
            buys = txns.get("buys", 1)
            sells = txns.get("sells", 1)
            
            token_data = TokenData(
                address=base_token.get("address", ""),
                name=base_token.get("name", "Unknown"),
                symbol=base_token.get("symbol", "???"),
                price_usd=float(pair.get("priceUsd", 0) or 0),
                price_change_24h=float(price_change.get("h24", 0) or 0),
                market_cap=float(pair.get("fdv", 0) or 0),
                liquidity=float(liquidity.get("usd", 0) or 0),
                volume_24h=float(volume.get("h24", 0) or 0),
                holders=int(pair.get("holders", 0) or 0),
                buyers_24h=buys,
                sellers_24h=sells,
                buy_sell_ratio=round(buys / max(sells, 1), 2),
                age_hours=round(age_hours, 1),
                risk_analysis=calculate_risk_score(pair)
            )
            tokens.append(token_data)
        except Exception as e:
            logger.error(f"Error processing token: {e}")
            continue
    
    return tokens

@api_router.get("/tokens/{address}", response_model=TokenData)
async def get_token_details(address: str):
    """Get detailed information about a specific token"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            response = await client_http.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{address}"
            )
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                if pairs:
                    pair = pairs[0]  # Get the main pair
                    base_token = pair.get("baseToken", {})
                    price_change = pair.get("priceChange", {})
                    volume = pair.get("volume", {})
                    liquidity = pair.get("liquidity", {})
                    txns = pair.get("txns", {}).get("h24", {})
                    
                    created_at = pair.get("pairCreatedAt", 0)
                    age_hours = (datetime.now(timezone.utc).timestamp() * 1000 - created_at) / (1000 * 60 * 60) if created_at else 0
                    
                    return TokenData(
                        address=address,
                        name=base_token.get("name", "Unknown"),
                        symbol=base_token.get("symbol", "???"),
                        price_usd=float(pair.get("priceUsd", 0) or 0),
                        price_change_24h=float(price_change.get("h24", 0) or 0),
                        market_cap=float(pair.get("fdv", 0) or 0),
                        liquidity=float(liquidity.get("usd", 0) or 0),
                        volume_24h=float(volume.get("h24", 0) or 0),
                        holders=int(pair.get("holders", 0) or 0),
                        buyers_24h=txns.get("buys", 0),
                        sellers_24h=txns.get("sells", 0),
                        buy_sell_ratio=round(txns.get("buys", 1) / max(txns.get("sells", 1), 1), 2),
                        age_hours=round(age_hours, 1),
                        risk_analysis=calculate_risk_score(pair)
                    )
    except Exception as e:
        logger.error(f"Error fetching token details: {e}")
    
    raise HTTPException(status_code=404, detail="Token not found")

# ============== TRADING OPPORTUNITIES ==============

@api_router.get("/opportunities", response_model=List[TradeOpportunity])
async def get_trading_opportunities():
    """Get AI-suggested trading opportunities"""
    tokens = await scan_tokens(limit=10)
    opportunities = []
    
    for token in tokens:
        if token.risk_analysis and token.risk_analysis.risk_score < 70:
            # Calculate potential profit based on momentum
            if token.buy_sell_ratio > 1.5 and token.price_change_24h > 5:
                confidence = min(90, 50 + token.buy_sell_ratio * 10 + token.price_change_24h * 0.5)
                potential_profit = min(200, token.price_change_24h * 2)
                
                opportunity = TradeOpportunity(
                    token=token,
                    suggested_action="BUY",
                    confidence=round(confidence, 1),
                    potential_profit=round(potential_profit, 1),
                    risk_level="LOW" if token.risk_analysis.risk_score < 40 else "MEDIUM",
                    reason=f"Strong momentum: {token.buy_sell_ratio}x buy/sell ratio, +{token.price_change_24h}% 24h"
                )
                opportunities.append(opportunity)
    
    return sorted(opportunities, key=lambda x: x.confidence, reverse=True)[:5]

# ============== TRADES ENDPOINTS ==============

@api_router.post("/trades", response_model=Trade)
async def create_trade(trade_data: TradeCreate):
    """Create a new trade (paper or real)"""
    settings = await get_settings()
    
    # Check trade limits
    open_trades = await db.trades.count_documents({"status": "OPEN"})
    if open_trades >= settings.max_parallel_trades:
        raise HTTPException(status_code=400, detail="Maximum parallel trades reached")
    
    # Calculate take profit and stop loss prices
    take_profit_price = trade_data.price_entry * (1 + trade_data.take_profit_percent / 100)
    stop_loss_price = trade_data.price_entry * (1 - trade_data.stop_loss_percent / 100)
    
    # Calculate token amount
    amount_tokens = trade_data.amount_sol / trade_data.price_entry if trade_data.price_entry > 0 else 0
    
    trade = Trade(
        token_address=trade_data.token_address,
        token_symbol=trade_data.token_symbol,
        token_name=trade_data.token_name,
        trade_type=trade_data.trade_type,
        amount_sol=trade_data.amount_sol,
        amount_tokens=amount_tokens,
        price_entry=trade_data.price_entry,
        price_current=trade_data.price_entry,
        take_profit=take_profit_price,
        stop_loss=stop_loss_price,
        paper_trade=trade_data.paper_trade,
        wallet_address=trade_data.wallet_address
    )
    
    doc = trade.model_dump()
    doc["opened_at"] = doc["opened_at"].isoformat()
    await db.trades.insert_one(doc)
    
    return trade

@api_router.get("/trades", response_model=List[Trade])
async def get_trades(status: Optional[str] = None):
    """Get all trades, optionally filtered by status"""
    query = {}
    if status:
        query["status"] = status
    
    trades = await db.trades.find(query, {"_id": 0}).sort("opened_at", -1).to_list(100)
    
    for trade in trades:
        if isinstance(trade.get("opened_at"), str):
            trade["opened_at"] = datetime.fromisoformat(trade["opened_at"])
        if isinstance(trade.get("closed_at"), str):
            trade["closed_at"] = datetime.fromisoformat(trade["closed_at"])
    
    return trades

@api_router.get("/trades/{trade_id}", response_model=Trade)
async def get_trade(trade_id: str):
    """Get a specific trade"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if isinstance(trade.get("opened_at"), str):
        trade["opened_at"] = datetime.fromisoformat(trade["opened_at"])
    if isinstance(trade.get("closed_at"), str):
        trade["closed_at"] = datetime.fromisoformat(trade["closed_at"])
    
    return Trade(**trade)

@api_router.put("/trades/{trade_id}/close")
async def close_trade(trade_id: str, exit_price: float):
    """Close a trade"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Calculate PnL
    pnl = (exit_price - trade["price_entry"]) * trade["amount_tokens"]
    pnl_percent = ((exit_price / trade["price_entry"]) - 1) * 100
    
    update_data = {
        "status": "CLOSED",
        "price_exit": exit_price,
        "price_current": exit_price,
        "pnl": round(pnl, 6),
        "pnl_percent": round(pnl_percent, 2),
        "closed_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trades.update_one({"id": trade_id}, {"$set": update_data})
    
    return {"success": True, "pnl": pnl, "pnl_percent": pnl_percent}

# ============== PORTFOLIO ENDPOINTS ==============

@api_router.get("/portfolio", response_model=PortfolioSummary)
async def get_portfolio_summary():
    """Get portfolio summary and statistics"""
    trades = await db.trades.find({}, {"_id": 0}).to_list(1000)
    
    open_trades = [t for t in trades if t.get("status") == "OPEN"]
    closed_trades = [t for t in trades if t.get("status") == "CLOSED"]
    
    total_value = sum(t.get("amount_sol", 0) for t in open_trades)
    total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
    
    winning_trades = [t for t in closed_trades if t.get("pnl", 0) > 0]
    win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0
    
    pnls = [t.get("pnl", 0) for t in closed_trades]
    best_trade = max(pnls) if pnls else 0
    worst_trade = min(pnls) if pnls else 0
    
    initial_capital = sum(t.get("amount_sol", 0) for t in closed_trades)
    total_pnl_percent = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
    
    return PortfolioSummary(
        total_value_sol=round(total_value, 4),
        total_pnl=round(total_pnl, 6),
        total_pnl_percent=round(total_pnl_percent, 2),
        open_trades=len(open_trades),
        closed_trades=len(closed_trades),
        win_rate=round(win_rate, 1),
        best_trade_pnl=round(best_trade, 6),
        worst_trade_pnl=round(worst_trade, 6)
    )

# ============== WALLET ENDPOINTS ==============

@api_router.get("/wallet/balance/{address}")
async def get_wallet_balance(address: str):
    """Get wallet SOL balance"""
    sol_price = await get_sol_price()
    
    # In production, this would query the Solana RPC
    # For now, return mock data
    return {
        "address": address,
        "balance_sol": 0.0,
        "balance_usd": 0.0,
        "sol_price": sol_price
    }

@api_router.get("/market/sol-price")
async def get_current_sol_price():
    """Get current SOL price"""
    price = await get_sol_price()
    return {"price": price, "currency": "USD"}

# ============== HEALTH CHECK ==============

@api_router.get("/")
async def root():
    return {"message": "Pump.fun Trading Terminal API", "version": "1.0.0"}

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
