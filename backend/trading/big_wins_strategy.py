"""
Big Wins Trading Strategy

Optimiert für große Gewinne pro Trade statt viele kleine Gewinne.

Strategie:
- Mehrstufige Take-Profit Levels (25%, 60%, 120%)
- Intelligentes Trailing Profit für Pump-Runs
- Strenge Entry-Qualitätsfilter
- Schutz großer Gewinne durch dynamischen Stop-Loss

Zielwerte:
- Average Win: +35% bis +80%
- Average Loss: -10% bis -15%
- Winrate: 30-45%
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ============== BIG WINS STRATEGY CONFIGURATION ==============
STRATEGY_CONFIG = {
    # ===== MEHRSTUFIGE TAKE-PROFIT LEVELS =====
    "take_profit_enabled": True,
    "take_profit_levels": [
        {"level": "TP1", "percent": 25, "sell_percent": 30},   # +25% → 30% verkaufen
        {"level": "TP2", "percent": 60, "sell_percent": 30},   # +60% → weitere 30% verkaufen
        {"level": "TP3", "percent": 120, "sell_percent": 20},  # +120% → weitere 20% verkaufen
        {"level": "RUNNER", "percent": None, "sell_percent": 20}  # Runner: 20% laufen lassen
    ],
    
    # ===== TRAILING PROFIT SYSTEM =====
    "trailing_profit_enabled": True,
    "trailing_start_percent": 35,      # Trailing aktivieren ab +35%
    "trailing_stop_percent": 15,       # 15% unter Peak verkaufen
    
    # ===== MINIMUM PROFIT RULE =====
    "minimum_profit_before_sell": 15,  # Kein Verkauf unter +15%
    
    # ===== STOP LOSS SETTINGS =====
    "stop_loss_percent": 15,           # -15% Standard Stop Loss
    "stop_loss_range": (12, 18),       # Akzeptabler Bereich: -12% bis -18%
    
    # ===== GEWINNER SCHÜTZEN =====
    "protect_winners_enabled": True,
    "protect_at_percent": 100,         # Bei +100% Gewinn
    "protected_stop_percent": 40,      # Stop auf +40% setzen
    
    # ===== ENTRY QUALITY FILTER =====
    "entry_quality": {
        "min_liquidity_usd": 40000,    # Mindestens $40k Liquidität
        "min_volume_spike": 2.0,       # 2x Volume Spike
        "min_market_cap_usd": 80000,   # Min $80k Market Cap
        "max_market_cap_usd": 3000000, # Max $3M Market Cap
        "max_age_hours": 12,           # Max 12 Stunden alt
        "min_holders": 50,             # Mindestens 50 Holder
    },
    
    # ===== PUMP DETECTION =====
    "pump_detection": {
        "volume_1m_multiplier": 1.8,   # volume_1m > volume_5m_avg × 1.8
        "price_change_1m_min": 3.0,    # Min 3% Price Change in 1m
        "buyers_dominance": 1.5,       # Buyers > Sellers × 1.5
    },
    
    # ===== SLIPPAGE KONTROLLE =====
    "max_slippage_percent": 8,         # Max 8% Slippage
    "slippage_warning_percent": 5,     # Warnung ab 5%
    
    # ===== POSITION SIZING =====
    "position_sizing": {
        "max_trades": 30,              # Max 30 parallele Trades (fokussierter)
        "trade_percent": 2.0,          # 2% des Wallets pro Trade
        "max_trade_sol": 0.1,          # Max 0.1 SOL pro Trade
        "min_trade_sol": 0.01,         # Min 0.01 SOL pro Trade
        "max_capital_percent": 60,     # Max 60% des Kapitals in Trades
    },
    
    # ===== RISK MANAGEMENT =====
    "risk_management": {
        "daily_loss_limit_percent": 20,   # Max 20% Tagesverlust
        "max_loss_streak": 8,             # Max 8 Verlusttrades in Folge
        "cooldown_after_loss_streak": 300, # 5min Pause nach Verlustserie
    },
}


@dataclass
class TradePosition:
    """Repräsentiert eine offene Trade-Position mit Big Wins Logik"""
    trade_id: str
    token_address: str
    token_symbol: str
    entry_price: float
    current_price: float
    amount_sol: float
    remaining_percent: float = 100.0  # Verbleibende Position (startet bei 100%)
    peak_price: float = 0.0
    trailing_stop: Optional[float] = None
    stop_loss: float = 0.0
    levels_hit: List[str] = field(default_factory=list)
    protected: bool = False
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def pnl_percent(self) -> float:
        if self.entry_price <= 0:
            return 0
        return ((self.current_price / self.entry_price) - 1) * 100
    
    @property
    def distance_from_peak_percent(self) -> float:
        if self.peak_price <= 0:
            return 0
        return ((self.current_price / self.peak_price) - 1) * 100


class BigWinsStrategy:
    """
    Big Wins Trading Strategie
    
    Ziel: Große Gewinne laufen lassen, kleine Verluste akzeptieren.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or STRATEGY_CONFIG
        self.stats = {
            "trades_opened": 0,
            "trades_closed": 0,
            "tp1_hits": 0,
            "tp2_hits": 0,
            "tp3_hits": 0,
            "runners_closed": 0,
            "trailing_stops": 0,
            "stop_losses": 0,
            "protected_stops": 0,
            "total_profit_percent": 0,
            "total_loss_percent": 0,
            "biggest_win_percent": 0,
            "biggest_loss_percent": 0,
        }
    
    def check_entry_quality(self, token_data: Dict) -> Tuple[bool, List[str]]:
        """
        Prüft ob ein Token die Entry-Qualitätsfilter erfüllt.
        
        Returns: (passes_filter, rejection_reasons)
        """
        entry_config = self.config["entry_quality"]
        reasons = []
        
        # Liquidität prüfen
        liquidity = float(token_data.get("liquidity", {}).get("usd", 0) or 0)
        if liquidity < entry_config["min_liquidity_usd"]:
            reasons.append(f"Liquidität zu niedrig: ${liquidity:.0f} < ${entry_config['min_liquidity_usd']}")
        
        # Market Cap prüfen
        market_cap = float(token_data.get("fdv", 0) or token_data.get("market_cap", 0) or 0)
        if market_cap < entry_config["min_market_cap_usd"]:
            reasons.append(f"Market Cap zu niedrig: ${market_cap:.0f}")
        if market_cap > entry_config["max_market_cap_usd"]:
            reasons.append(f"Market Cap zu hoch: ${market_cap:.0f}")
        
        # Token-Alter prüfen
        created_at = token_data.get("pairCreatedAt", 0)
        if created_at:
            age_hours = (datetime.now(timezone.utc).timestamp() * 1000 - created_at) / 1000 / 3600
            if age_hours > entry_config["max_age_hours"]:
                reasons.append(f"Token zu alt: {age_hours:.1f}h")
        
        # Volume Spike prüfen
        volume_5m = float(token_data.get("volume", {}).get("m5", 0) or 0)
        volume_1h = float(token_data.get("volume", {}).get("h1", 0) or 0)
        avg_5m_volume = volume_1h / 12 if volume_1h > 0 else 0
        
        if avg_5m_volume > 0:
            volume_spike = volume_5m / avg_5m_volume
            if volume_spike < entry_config["min_volume_spike"]:
                reasons.append(f"Volume Spike zu niedrig: {volume_spike:.1f}x < {entry_config['min_volume_spike']}x")
        
        passes = len(reasons) == 0
        return (passes, reasons)
    
    def check_pump_signal(self, token_data: Dict) -> Tuple[bool, float, List[str]]:
        """
        Prüft ob ein Pump-Signal vorliegt.
        
        Returns: (is_pump, confidence, signals)
        """
        pump_config = self.config["pump_detection"]
        signals = []
        confidence = 0
        
        # Volume 1m vs 5m average
        volume_5m = float(token_data.get("volume", {}).get("m5", 0) or 0)
        volume_1m = volume_5m / 5 if volume_5m > 0 else 0
        volume_5m_avg = volume_5m / 5
        
        if volume_5m_avg > 0:
            volume_ratio = volume_1m / volume_5m_avg if volume_5m_avg > 0 else 0
            if volume_ratio >= pump_config["volume_1m_multiplier"]:
                confidence += 35
                signals.append(f"Volume Spike: {volume_ratio:.1f}x")
        
        # Price Change
        price_change_5m = float(token_data.get("priceChange", {}).get("m5", 0) or 0)
        price_change_1m = price_change_5m / 3  # Approximate
        
        if price_change_1m >= pump_config["price_change_1m_min"]:
            confidence += 30
            signals.append(f"Price Momentum: +{price_change_1m:.1f}%")
        
        # Buyer Dominance
        txns = token_data.get("txns", {}).get("m5", {})
        buys = txns.get("buys", 0) or 0
        sells = txns.get("sells", 0) or 0
        
        if sells > 0 and buys / max(sells, 1) >= pump_config["buyers_dominance"]:
            confidence += 25
            signals.append(f"Buyer Dominance: {buys}/{sells}")
        elif buys > 5 and sells == 0:
            confidence += 35
            signals.append(f"Pure Buy Pressure: {buys} buys")
        
        # Liquidity Quality
        liquidity = float(token_data.get("liquidity", {}).get("usd", 0) or 0)
        if liquidity >= 50000:
            confidence += 10
            signals.append(f"Good Liquidity: ${liquidity:.0f}")
        
        is_pump = confidence >= 60
        return (is_pump, confidence, signals)
    
    def calculate_take_profit_levels(self, entry_price: float) -> Dict[str, float]:
        """
        Berechnet die Take-Profit Preisniveaus.
        
        Returns: {"TP1": price, "TP2": price, "TP3": price}
        """
        levels = {}
        for tp in self.config["take_profit_levels"]:
            if tp["percent"] is not None:
                levels[tp["level"]] = entry_price * (1 + tp["percent"] / 100)
        return levels
    
    def calculate_stop_loss(self, entry_price: float) -> float:
        """Berechnet den Stop-Loss Preis."""
        return entry_price * (1 - self.config["stop_loss_percent"] / 100)
    
    def update_position(self, position: TradePosition) -> Dict:
        """
        Aktualisiert eine Position und prüft auf Exits.
        
        Returns: {
            "action": "HOLD" | "PARTIAL_SELL" | "FULL_SELL",
            "sell_percent": float,
            "reason": str,
            "new_stop_loss": float (optional)
        }
        """
        result = {
            "action": "HOLD",
            "sell_percent": 0,
            "reason": None,
            "new_stop_loss": None,
            "logs": []
        }
        
        pnl = position.pnl_percent
        entry_price = position.entry_price
        current_price = position.current_price
        
        # Update Peak Price
        if current_price > position.peak_price:
            position.peak_price = current_price
            result["logs"].append(f"New peak: ${current_price:.8f} (+{pnl:.1f}%)")
        
        # ===== CHECK STOP LOSS =====
        if current_price <= position.stop_loss:
            result["action"] = "FULL_SELL"
            result["sell_percent"] = position.remaining_percent
            if position.protected:
                result["reason"] = "PROTECTED_STOP"
                self.stats["protected_stops"] += 1
            else:
                result["reason"] = "STOP_LOSS"
                self.stats["stop_losses"] += 1
            return result
        
        # ===== CHECK MINIMUM PROFIT RULE =====
        min_profit = self.config["minimum_profit_before_sell"]
        if pnl > 0 and pnl < min_profit:
            # Nicht verkaufen unter Minimum
            result["logs"].append(f"Under min profit ({pnl:.1f}% < {min_profit}%)")
            return result
        
        # ===== CHECK TAKE PROFIT LEVELS =====
        if self.config["take_profit_enabled"]:
            tp_levels = self.config["take_profit_levels"]
            
            for tp in tp_levels:
                level_name = tp["level"]
                target_percent = tp["percent"]
                sell_percent = tp["sell_percent"]
                
                if target_percent is None:  # Runner
                    continue
                
                if level_name not in position.levels_hit and pnl >= target_percent:
                    position.levels_hit.append(level_name)
                    result["action"] = "PARTIAL_SELL"
                    result["sell_percent"] = sell_percent
                    result["reason"] = f"{level_name}_HIT"
                    
                    # Update stats
                    if level_name == "TP1":
                        self.stats["tp1_hits"] += 1
                    elif level_name == "TP2":
                        self.stats["tp2_hits"] += 1
                    elif level_name == "TP3":
                        self.stats["tp3_hits"] += 1
                    
                    result["logs"].append(f"{level_name} hit at +{pnl:.1f}%! Selling {sell_percent}%")
                    return result
        
        # ===== CHECK WINNER PROTECTION =====
        if self.config["protect_winners_enabled"] and not position.protected:
            protect_at = self.config["protect_at_percent"]
            protected_stop = self.config["protected_stop_percent"]
            
            if pnl >= protect_at:
                position.protected = True
                new_stop = entry_price * (1 + protected_stop / 100)
                position.stop_loss = new_stop
                result["new_stop_loss"] = new_stop
                result["logs"].append(f"Winner protected! SL moved to +{protected_stop}%")
        
        # ===== CHECK TRAILING PROFIT =====
        if self.config["trailing_profit_enabled"]:
            trailing_start = self.config["trailing_start_percent"]
            trailing_stop_pct = self.config["trailing_stop_percent"]
            
            if pnl >= trailing_start:
                # Trailing ist aktiv
                distance_from_peak = position.distance_from_peak_percent
                
                if distance_from_peak <= -trailing_stop_pct:
                    # Trailing Stop getriggert
                    result["action"] = "FULL_SELL"
                    result["sell_percent"] = position.remaining_percent
                    result["reason"] = "TRAILING_STOP"
                    self.stats["trailing_stops"] += 1
                    result["logs"].append(f"Trailing stop at {pnl:.1f}% (peak was +{((position.peak_price/entry_price)-1)*100:.1f}%)")
                    return result
                else:
                    result["logs"].append(f"Trailing active: {distance_from_peak:.1f}% from peak")
        
        return result
    
    def calculate_position_size(self, wallet_balance: float, token_data: Dict) -> float:
        """
        Berechnet die optimale Positionsgröße.
        
        Returns: Position size in SOL
        """
        pos_config = self.config["position_sizing"]
        
        # Basis-Position
        base_size = wallet_balance * (pos_config["trade_percent"] / 100)
        
        # Limits anwenden
        size = max(pos_config["min_trade_sol"], min(base_size, pos_config["max_trade_sol"]))
        
        return round(size, 4)
    
    def check_slippage(self, expected_price: float, actual_price: float) -> Tuple[bool, float, str]:
        """
        Prüft ob Slippage akzeptabel ist.
        
        Returns: (acceptable, slippage_percent, warning_message)
        """
        if expected_price <= 0:
            return (True, 0, "")
        
        slippage = abs((actual_price / expected_price) - 1) * 100
        max_slippage = self.config["max_slippage_percent"]
        warning_level = self.config["slippage_warning_percent"]
        
        if slippage > max_slippage:
            return (False, slippage, f"Slippage zu hoch: {slippage:.1f}% > {max_slippage}%")
        elif slippage > warning_level:
            return (True, slippage, f"Slippage Warnung: {slippage:.1f}%")
        
        return (True, slippage, "")
    
    def get_strategy_summary(self) -> Dict:
        """Gibt eine Zusammenfassung der Strategie-Performance zurück."""
        total_trades = self.stats["trades_closed"]
        wins = self.stats["tp1_hits"] + self.stats["tp2_hits"] + self.stats["tp3_hits"] + self.stats["runners_closed"]
        losses = self.stats["stop_losses"] + self.stats["protected_stops"]
        
        return {
            "strategy_name": "Big Wins",
            "total_trades_closed": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / max(total_trades, 1)) * 100,
            "tp_breakdown": {
                "TP1 (+25%)": self.stats["tp1_hits"],
                "TP2 (+60%)": self.stats["tp2_hits"],
                "TP3 (+120%)": self.stats["tp3_hits"],
                "Trailing Stops": self.stats["trailing_stops"],
            },
            "protection": {
                "protected_exits": self.stats["protected_stops"],
                "stop_losses": self.stats["stop_losses"],
            },
            "biggest_win": f"+{self.stats['biggest_win_percent']:.1f}%",
            "biggest_loss": f"{self.stats['biggest_loss_percent']:.1f}%",
            "config": {
                "take_profit_levels": "25% / 60% / 120%",
                "trailing_start": f"+{self.config['trailing_start_percent']}%",
                "trailing_stop": f"-{self.config['trailing_stop_percent']}%",
                "stop_loss": f"-{self.config['stop_loss_percent']}%",
                "min_profit_to_sell": f"+{self.config['minimum_profit_before_sell']}%",
            }
        }


# Global Strategy Instance
big_wins_strategy = BigWinsStrategy()
