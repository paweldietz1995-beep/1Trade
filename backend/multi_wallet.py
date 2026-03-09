"""
Multi-Wallet Manager für Pump.fun Trading Bot
Verwaltet 10+ Wallets mit zentraler Handelslogik
"""

import json
import os
import base58
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

@dataclass
class WalletState:
    """Repräsentiert den Zustand eines einzelnen Wallets"""
    wallet_id: int
    public_key: str
    private_key_b58: str  # Wird nur intern verwendet, nie geloggt!
    balance_sol: float = 0.0
    open_trades_count: int = 0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl_sol: float = 0.0
    capital_in_trades: float = 0.0
    last_balance_update: Optional[datetime] = None
    is_active: bool = True
    max_trades: int = 120  # Max Trades pro Wallet
    consecutive_losses: int = 0  # NEU: Verlustserie pro Wallet
    
    @property
    def available_capital(self) -> float:
        """Verfügbares Kapital für neue Trades"""
        return max(0, self.balance_sol - self.capital_in_trades)
    
    @property
    def win_rate(self) -> float:
        """Gewinnrate in Prozent"""
        if self.total_trades == 0:
            return 0.0
        return (self.wins / self.total_trades) * 100
    
    @property
    def can_trade(self) -> bool:
        """Prüft ob Wallet noch traden kann"""
        return (
            self.is_active and 
            self.open_trades_count < self.max_trades and
            self.available_capital > 0.005  # Mindestens 0.005 SOL frei
        )
    
    @property
    def loss_streak_reached(self) -> bool:
        """Prüft ob Loss-Streak-Limit erreicht (wird extern gesetzt)"""
        # Wird vom MultiWalletManager geprüft
        return False
    
    def to_dict(self) -> Dict:
        """Serialisiert Wallet-Daten (ohne Private Key!)"""
        return {
            "wallet_id": self.wallet_id,
            "public_key": self.public_key,
            "balance_sol": round(self.balance_sol, 6),
            "open_trades_count": self.open_trades_count,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "total_pnl_sol": round(self.total_pnl_sol, 6),
            "capital_in_trades": round(self.capital_in_trades, 6),
            "available_capital": round(self.available_capital, 6),
            "win_rate": round(self.win_rate, 2),
            "is_active": self.is_active,
            "max_trades": self.max_trades,
            "can_trade": self.can_trade,
            "consecutive_losses": self.consecutive_losses
        }


class MultiWalletManager:
    """
    Zentrale Verwaltung für mehrere Trading-Wallets
    
    Features:
    - Lädt Wallets aus JSON-Konfiguration
    - Verteilt Trades nach freiem Kapital
    - Verhindert Doppelkäufe (globale Token-Sperre)
    - Aktualisiert Balances regelmäßig
    """
    
    def __init__(self, config_path: str = None):
        self.wallets: Dict[int, WalletState] = {}
        self.active_tokens: Dict[str, int] = {}  # token_mint -> wallet_id (Sperre)
        self.round_robin_index: int = 0
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), "wallets_config.json"
        )
        self.is_initialized: bool = False
        self.distribution_strategy: str = "free_capital"  # round_robin, free_capital, least_trades
        self.loss_streak_limit: int = 50  # NEU: Pro-Wallet Loss-Streak-Limit
        
        # Statistiken
        self.total_trades_executed: int = 0
        self.total_pnl_all_wallets: float = 0.0
        
    async def initialize(self) -> bool:
        """
        Initialisiert den Manager und lädt Wallets.
        Unterstützt sowohl JSON-Datei als auch Umgebungsvariablen.
        """
        try:
            # Versuche zuerst JSON-Datei
            if os.path.exists(self.config_path):
                logger.info(f"📁 Lade Wallets aus {self.config_path}")
                await self._load_from_json()
            else:
                # Fallback: Umgebungsvariablen WALLET_1, WALLET_2, etc.
                logger.info("📁 Keine JSON-Datei gefunden, prüfe Umgebungsvariablen...")
                await self._load_from_env()
            
            if not self.wallets:
                # Letzter Fallback: Einzelnes Wallet aus SOLANA_PRIVATE_KEY
                logger.info("📁 Fallback auf SOLANA_PRIVATE_KEY...")
                await self._load_single_wallet()
            
            if self.wallets:
                self.is_initialized = True
                logger.info(f"✅ MultiWalletManager initialisiert mit {len(self.wallets)} Wallet(s)")
                for wid, wallet in self.wallets.items():
                    logger.info(f"   Wallet {wid}: {wallet.public_key[:8]}...{wallet.public_key[-6:]}")
                return True
            else:
                logger.warning("⚠️ Keine Wallets konfiguriert - Read-Only Modus")
                return False
                
        except Exception as e:
            logger.error(f"❌ MultiWalletManager Initialisierung fehlgeschlagen: {e}")
            return False
    
    async def _load_from_json(self):
        """Lädt Wallets aus JSON-Konfigurationsdatei"""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            
            wallet_keys = config.get("wallets", [])
            max_trades_per_wallet = config.get("max_trades_per_wallet", 120)
            self.distribution_strategy = config.get("distribution_strategy", "free_capital")
            self.loss_streak_limit = config.get("loss_streak_limit", 50)  # NEU: Aus Config laden
            
            for i, key_data in enumerate(wallet_keys):
                if isinstance(key_data, str):
                    # Einfaches Format: nur Private Key
                    private_key = key_data
                elif isinstance(key_data, dict):
                    # Erweitertes Format mit Optionen
                    private_key = key_data.get("private_key")
                    max_trades_per_wallet = key_data.get("max_trades", max_trades_per_wallet)
                else:
                    continue
                
                if private_key:
                    try:
                        # Public Key aus Private Key ableiten
                        from solders.keypair import Keypair
                        key_bytes = base58.b58decode(private_key)
                        keypair = Keypair.from_bytes(key_bytes)
                        public_key = str(keypair.pubkey())
                        
                        self.wallets[i] = WalletState(
                            wallet_id=i,
                            public_key=public_key,
                            private_key_b58=private_key,
                            max_trades=max_trades_per_wallet
                        )
                        logger.info(f"   ✅ Wallet {i} geladen: {public_key[:8]}...")
                    except Exception as e:
                        logger.error(f"   ❌ Wallet {i} fehlerhaft: {e}")
                        
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON-Parsing-Fehler in {self.config_path}: {e}")
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Wallet-Konfiguration: {e}")
    
    async def _load_from_env(self):
        """Lädt Wallets aus Umgebungsvariablen WALLET_0, WALLET_1, etc."""
        for i in range(20):  # Max 20 Wallets
            env_key = f"WALLET_{i}"
            private_key = os.environ.get(env_key)
            
            if private_key:
                try:
                    from solders.keypair import Keypair
                    key_bytes = base58.b58decode(private_key)
                    keypair = Keypair.from_bytes(key_bytes)
                    public_key = str(keypair.pubkey())
                    
                    self.wallets[i] = WalletState(
                        wallet_id=i,
                        public_key=public_key,
                        private_key_b58=private_key
                    )
                    logger.info(f"   ✅ Wallet {i} aus {env_key} geladen")
                except Exception as e:
                    logger.error(f"   ❌ {env_key} fehlerhaft: {e}")
    
    async def _load_single_wallet(self):
        """Fallback: Lädt einzelnes Wallet aus SOLANA_PRIVATE_KEY"""
        private_key = os.environ.get("SOLANA_PRIVATE_KEY")
        
        if private_key:
            try:
                from solders.keypair import Keypair
                
                # Unterstütze Base58 und JSON-Array Format
                if private_key.startswith("["):
                    key_array = json.loads(private_key)
                    key_bytes = bytes(key_array)
                else:
                    key_bytes = base58.b58decode(private_key)
                
                keypair = Keypair.from_bytes(key_bytes)
                public_key = str(keypair.pubkey())
                
                self.wallets[0] = WalletState(
                    wallet_id=0,
                    public_key=public_key,
                    private_key_b58=base58.b58encode(key_bytes).decode()
                )
                logger.info(f"   ✅ Hauptwallet geladen: {public_key[:8]}...")
            except Exception as e:
                logger.error(f"   ❌ SOLANA_PRIVATE_KEY fehlerhaft: {e}")
    
    def get_wallet(self, wallet_id: int) -> Optional[WalletState]:
        """Gibt Wallet nach ID zurück"""
        return self.wallets.get(wallet_id)
    
    def get_all_wallets(self) -> List[WalletState]:
        """Gibt alle aktiven Wallets zurück"""
        return list(self.wallets.values())
    
    def get_keypair(self, wallet_id: int):
        """Gibt Keypair für Signierung zurück"""
        wallet = self.wallets.get(wallet_id)
        if wallet:
            from solders.keypair import Keypair
            key_bytes = base58.b58decode(wallet.private_key_b58)
            return Keypair.from_bytes(key_bytes)
        return None
    
    def select_wallet_for_trade(self, token_mint: str = None) -> Optional[WalletState]:
        """
        Wählt das beste Wallet für einen neuen Trade.
        
        Strategien:
        - free_capital: Wallet mit meistem freien Kapital
        - round_robin: Der Reihe nach
        - least_trades: Wallet mit wenigsten offenen Trades
        
        Returns: WalletState oder None wenn kein Wallet verfügbar
        """
        # Prüfe Token-Sperre (strikte Doppelkauf-Verhinderung)
        if token_mint and token_mint in self.active_tokens:
            logger.debug(f"🔒 Token {token_mint[:8]}... bereits von Wallet {self.active_tokens[token_mint]} gehalten")
            return None
        
        # Filtere verfügbare Wallets (inkl. Loss-Streak-Prüfung)
        available_wallets = [
            w for w in self.wallets.values() 
            if w.can_trade and w.consecutive_losses < self.loss_streak_limit
        ]
        
        # Logge Wallets die wegen Loss-Streak ausgeschlossen sind
        excluded_by_loss_streak = [
            w for w in self.wallets.values()
            if w.can_trade and w.consecutive_losses >= self.loss_streak_limit
        ]
        if excluded_by_loss_streak:
            for w in excluded_by_loss_streak:
                logger.warning(f"⚠️ Wallet {w.wallet_id} wegen Loss-Streak ausgeschlossen ({w.consecutive_losses}/{self.loss_streak_limit})")
        
        if not available_wallets:
            if excluded_by_loss_streak:
                logger.warning(f"⚠️ Alle Wallets haben Loss-Streak-Limit erreicht – keine neuen Trades")
            else:
                logger.warning("⚠️ Keine Wallets verfügbar für neuen Trade")
            return None
        
        if self.distribution_strategy == "free_capital":
            # Wallet mit meistem freien Kapital
            selected = max(available_wallets, key=lambda w: w.available_capital)
        elif self.distribution_strategy == "round_robin":
            # Round-Robin
            selected = available_wallets[self.round_robin_index % len(available_wallets)]
            self.round_robin_index += 1
        elif self.distribution_strategy == "least_trades":
            # Wallet mit wenigsten offenen Trades
            selected = min(available_wallets, key=lambda w: w.open_trades_count)
        else:
            # Default: Free Capital
            selected = max(available_wallets, key=lambda w: w.available_capital)
        
        logger.debug(f"📍 Wallet {selected.wallet_id} ausgewählt (Strategy: {self.distribution_strategy}, Capital: {selected.available_capital:.4f} SOL, LossStreak: {selected.consecutive_losses}/{self.loss_streak_limit})")
        return selected
    
    def lock_token(self, token_mint: str, wallet_id: int):
        """Sperrt Token für ein Wallet (verhindert Doppelkäufe)"""
        self.active_tokens[token_mint] = wallet_id
        logger.debug(f"🔒 Token {token_mint[:8]}... für Wallet {wallet_id} gesperrt")
    
    def unlock_token(self, token_mint: str):
        """Entsperrt Token nach Verkauf"""
        if token_mint in self.active_tokens:
            wallet_id = self.active_tokens.pop(token_mint)
            logger.debug(f"🔓 Token {token_mint[:8]}... entsperrt (war Wallet {wallet_id})")
    
    def is_token_locked(self, token_mint: str) -> bool:
        """Prüft ob Token bereits gehandelt wird"""
        return token_mint in self.active_tokens
    
    def update_wallet_stats(self, wallet_id: int, trade_result: Dict):
        """
        Aktualisiert Wallet-Statistiken nach Trade-Abschluss
        
        trade_result: {
            "pnl_sol": float,
            "pnl_percent": float,
            "is_win": bool
        }
        """
        wallet = self.wallets.get(wallet_id)
        if wallet:
            wallet.total_trades += 1
            if trade_result.get("is_win", False):
                wallet.wins += 1
                wallet.consecutive_losses = 0  # NEU: Bei Gewinn Verlustserie zurücksetzen
                logger.info(f"✅ Wallet {wallet_id}: Gewinn! Verlustserie zurückgesetzt")
            else:
                wallet.losses += 1
                wallet.consecutive_losses += 1  # NEU: Bei Verlust erhöhen
                logger.info(f"⚠️ Wallet {wallet_id}: Verlust! Verlustserie jetzt bei {wallet.consecutive_losses}/{self.loss_streak_limit}")
            wallet.total_pnl_sol += trade_result.get("pnl_sol", 0)
            
            # Globale Statistiken
            self.total_trades_executed += 1
            self.total_pnl_all_wallets += trade_result.get("pnl_sol", 0)
    
    def add_trade_to_wallet(self, wallet_id: int, trade_amount: float, token_mint: str):
        """Registriert neuen Trade bei Wallet"""
        wallet = self.wallets.get(wallet_id)
        if wallet:
            wallet.open_trades_count += 1
            wallet.capital_in_trades += trade_amount
            self.lock_token(token_mint, wallet_id)
    
    def remove_trade_from_wallet(self, wallet_id: int, trade_amount: float, token_mint: str):
        """Entfernt Trade von Wallet nach Schließung"""
        wallet = self.wallets.get(wallet_id)
        if wallet:
            wallet.open_trades_count = max(0, wallet.open_trades_count - 1)
            wallet.capital_in_trades = max(0, wallet.capital_in_trades - trade_amount)
            self.unlock_token(token_mint)
    
    def reset_wallet_loss_streak(self, wallet_id: int) -> bool:
        """
        Setzt die Verlustserie eines einzelnen Wallets zurück.
        Ermöglicht es, ein pausiertes Wallet wieder zu aktivieren.
        """
        wallet = self.wallets.get(wallet_id)
        if wallet:
            previous = wallet.consecutive_losses
            wallet.consecutive_losses = 0
            logger.info(f"🔄 Wallet {wallet_id}: Verlustserie manuell zurückgesetzt ({previous} -> 0)")
            return True
        return False
    
    def reset_all_loss_streaks(self) -> int:
        """
        Setzt die Verlustserie aller Wallets zurück.
        Returns: Anzahl der zurückgesetzten Wallets
        """
        count = 0
        for wallet_id, wallet in self.wallets.items():
            if wallet.consecutive_losses > 0:
                wallet.consecutive_losses = 0
                count += 1
        logger.info(f"🔄 Verlustserie für {count} Wallets zurückgesetzt")
        return count
    
    def get_wallets_at_loss_limit(self) -> List[WalletState]:
        """
        Gibt alle Wallets zurück, die ihr Loss-Streak-Limit erreicht haben.
        """
        return [
            w for w in self.wallets.values()
            if w.consecutive_losses >= self.loss_streak_limit
        ]
    
    async def update_all_balances(self, rpc_client=None) -> Dict:
        """
        Aktualisiert SOL-Balances für alle Wallets via direktem RPC.
        Sollte alle 30-60 Sekunden aufgerufen werden.
        """
        import httpx
        
        results = {"updated": 0, "errors": 0, "balances": {}}
        
        # Nutze Solana Mainnet RPC direkt
        rpc_url = "https://api.mainnet-beta.solana.com"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for wallet_id, wallet in self.wallets.items():
                try:
                    # Direkte RPC getBalance Abfrage
                    response = await client.post(
                        rpc_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": wallet_id,
                            "method": "getBalance",
                            "params": [wallet.public_key]
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if "result" in data and "value" in data["result"]:
                            # Lamports zu SOL konvertieren
                            balance_lamports = data["result"]["value"]
                            balance_sol = balance_lamports / 1_000_000_000
                            wallet.balance_sol = balance_sol
                            wallet.last_balance_update = datetime.now(timezone.utc)
                            results["updated"] += 1
                            results["balances"][wallet_id] = balance_sol
                            logger.debug(f"💰 Wallet {wallet_id}: {balance_sol:.6f} SOL")
                        else:
                            results["errors"] += 1
                            logger.warning(f"⚠️ Wallet {wallet_id}: Ungültige RPC-Antwort")
                    else:
                        results["errors"] += 1
                        logger.warning(f"⚠️ Wallet {wallet_id}: RPC-Fehler {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"❌ Balance-Update Wallet {wallet_id} fehlgeschlagen: {e}")
                    results["errors"] += 1
        
        total_balance = sum(results["balances"].values())
        logger.info(f"💰 Wallet-Balances aktualisiert: {results['updated']}/{len(self.wallets)} | Total: {total_balance:.4f} SOL")
        return results
    
    def get_aggregated_stats(self) -> Dict:
        """Aggregierte Statistiken über alle Wallets"""
        total_balance = sum(w.balance_sol for w in self.wallets.values())
        total_capital_in_trades = sum(w.capital_in_trades for w in self.wallets.values())
        total_open_trades = sum(w.open_trades_count for w in self.wallets.values())
        total_trades = sum(w.total_trades for w in self.wallets.values())
        total_wins = sum(w.wins for w in self.wallets.values())
        total_losses = sum(w.losses for w in self.wallets.values())
        total_pnl = sum(w.total_pnl_sol for w in self.wallets.values())
        wallets_at_loss_limit = self.get_wallets_at_loss_limit()
        tradeable_wallets = [w for w in self.wallets.values() if w.can_trade and w.consecutive_losses < self.loss_streak_limit]
        
        return {
            "wallet_count": len(self.wallets),
            "active_wallets": len([w for w in self.wallets.values() if w.is_active]),
            "tradeable_wallets": len(tradeable_wallets),
            "wallets_at_loss_limit": len(wallets_at_loss_limit),
            "loss_streak_limit": self.loss_streak_limit,
            "total_balance_sol": round(total_balance, 6),
            "total_capital_in_trades": round(total_capital_in_trades, 6),
            "total_available_capital": round(total_balance - total_capital_in_trades, 6),
            "total_open_trades": total_open_trades,
            "max_possible_trades": sum(w.max_trades for w in self.wallets.values()),
            "total_trades_executed": total_trades,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "overall_win_rate": round((total_wins / total_trades * 100) if total_trades > 0 else 0, 2),
            "total_pnl_sol": round(total_pnl, 6),
            "active_tokens_count": len(self.active_tokens),
            "distribution_strategy": self.distribution_strategy
        }
    
    def get_all_wallet_stats(self) -> List[Dict]:
        """Gibt Statistiken für alle Wallets zurück"""
        return [wallet.to_dict() for wallet in self.wallets.values()]
    
    def to_dict(self) -> Dict:
        """Serialisiert Manager-Status"""
        return {
            "is_initialized": self.is_initialized,
            "distribution_strategy": self.distribution_strategy,
            "aggregated": self.get_aggregated_stats(),
            "wallets": self.get_all_wallet_stats()
        }


# Singleton-Instanz
multi_wallet_manager = MultiWalletManager()
