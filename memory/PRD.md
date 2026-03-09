# Pump.fun Trading Bot - PRD v24

## Problem Statement
Automatisiertes Ultra-High-Frequency Trading-System für Pump.fun Tokens auf der Solana Blockchain mit 100+ simultanen Micro-Trades.

## System Status: ULTRA-HIGH-FREQUENCY MICRO-TRADE ENGINE V4 AKTIV

Letztes Update: 2026-03-09

---

## Changelog

### 2026-03-09 - Ultra-High-Frequency Micro-Trade Engine

**Neue Konfiguration für 100+ simultane Trades:**

| Parameter | Alt | Neu |
|-----------|-----|-----|
| max_parallel_trades | 30 | 120 |
| micro_trade_percent | 0.75% | 0.35% |
| max_capital_in_trades | - | 60% |
| scan_interval | 1.0s | 0.8s |
| take_profit | 10% | 8% |
| stop_loss | 7% | 6% |
| cooldown | 60s | 45s |

**Neue Features:**
- Capital Control: Max 60% des Wallets in aktiven Trades
- Ultra-Micro Positionen: 0.2-0.5% des Wallets pro Trade
- Schnellere Exits: 8% TP, 6% SL, 4% Trailing
- Performance Logging: TRADING ENGINE STATUS & SCANNER SUMMARY

### Beispiel Trade-Sizing (3 SOL Wallet):
```
micro_trade_percent = 0.35%
trade_size = 3 * 0.0035 = 0.0105 SOL pro Trade
max_capital = 60% = 1.8 SOL
max_possible_trades = 1.8 / 0.0105 = ~171 Trades
```

---

## Engine Konfiguration

```python
ENGINE_CONFIG = {
    # Scanning
    "scan_interval_seconds": 0.8,
    "max_tokens_per_scan": 3000,
    "max_open_trades": 120,
    
    # Micro-Trade Sizing
    "micro_trade_percent": 0.35,
    "max_micro_trade_sol": 0.015,
    "min_micro_trade_sol": 0.003,
    
    # Capital Control
    "max_capital_in_trades_percent": 60,
    
    # Exit Strategy
    "take_profit_percent": 8,
    "stop_loss_percent": 6,
    "trailing_stop_percent": 4,
    
    # Momentum Entry
    "momentum_volume_multiplier": 1.4,
    "min_price_change_1m": 2,
    "min_buy_sell_ratio": 1.05,
    
    # Cooldown
    "signal_cooldown_seconds": 45
}
```

---

## Performance Logging Format

### TRADING ENGINE STATUS
```
==================================================
📊 TRADING ENGINE STATUS
   open_trades: 87
   available_slots: 33
   capital_used: 0.94 SOL (31.3%)
   capital_available: 0.86 SOL
==================================================
```

### SCANNER SUMMARY
```
==================================================
📊 SCANNER SUMMARY
   tokens_scanned: 3200
   opportunities: 54
   new_tokens: 12
==================================================
```

---

## API Endpoints

### Auto-Trading Status (erweitert)
`GET /api/auto-trading/status`

Neue Felder:
```json
{
  "open_trades": 87,
  "available_slots": 33,
  "capital": {
    "in_trades_sol": 0.94,
    "used_percent": 31.3,
    "available_sol": 0.86,
    "max_percent": 60
  },
  "config": {
    "max_open_trades": 120,
    "micro_trade_percent": 0.35,
    "max_capital_in_trades_percent": 60,
    "signal_cooldown_seconds": 45
  }
}
```

---

## Momentum Entry Signal

Trades werden nur eröffnet wenn:
```
price_change_1m >= 2%
volume_1m >= 1.4x baseline
buyers_1m > sellers_1m
```

## Token Priorisierung

Momentum Score Formel:
```
score = (volume_growth * 0.35)
      + (buyers_1m * 0.25)
      + (price_change_1m * 0.20)
      + (price_acceleration * 0.20)
```

---

## Test-Ergebnisse

- **Backend Tests:** 74/77 bestanden (96%)
- **Frontend E2E Tests:** 37 bestanden (100%)
- **Scanner V3:** Alle Tests bestanden

---

## Nächste Schritte (P1)

1. **Realtime Launch Sniper** - Pump.fun / Raydium Pool Detection
2. **Performance Dashboard** - Erweiterte Statistiken
3. **Refactoring** - server.py modularisieren

## Zukünftige Features (P2)

1. **MEV Protection** - Sandwich-Attack Schutz
2. **Telegram Notifications**
3. **Jupiter Swap Integration**

---

## Credentials

- **PIN:** 1234
