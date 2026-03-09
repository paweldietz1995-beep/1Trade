# Pump.fun Trading Bot - PRD v22

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain mit vollständiger deutscher Benutzeroberfläche.

## System Status: 🚀 HIGH-FREQUENCY MOMENTUM SCALPER AKTIV

Letztes Update: 2026-03-09

---

## Changelog (2026-03-09)

### High-Frequency Momentum Scalping (Latest)
- **Scan-Intervall:** 1.0 Sekunde
- **Max Parallel Trades:** 30 (optimiert für realistisches Trading)
- **Trade Size:** 0.5-1% Wallet (~0.02 SOL pro Trade)
- **Ergebnis:** 30 aktive Trades parallel

### Momentum Score Formula:
```
score = (volume_growth * 0.35) + (buyers_1m * 0.25) + (price_1m * 0.20) + (accel * 0.20)
```

### Entry Conditions (1-minute based):
- `price_change_1m >= 2%`
- `volume_1m >= 1.5x baseline`
- `buyers_1m >= sellers_1m`

### New Token Priority:
- Token < 60s: +50 bonus
- Token < 120s: +30 bonus
- Token < 5min: +15 bonus

### Exit Strategy:
- Take Profit: 10% (8-12%)
- Stop Loss: 7% (6-8%)
- Trailing Stop: 4%
- Cooldown: 60 Sekunden

### Token Filters:
- min_liquidity: $500
- min_volume: $500
- min_buy_sell_ratio: 1.05

### Logging:
```
📊 SCANNER SUMMARY | tokens_scanned: 146 | opportunities: 23 | open_trades: 30
🔥 TOP MOMENTUM | 1. memeless score=96 | 2. XPD score=73 | 3. FMC score=67
✅ TRADE EXECUTED | token: ABC | size: 0.02 SOL | target_profit: 10%
```

---

## Implementierte Module (8/8 aktiv)

### 1. Market Scanner ✅
- **Intervall:** 2 Sekunden
- **Kapazität:** 200 Tokens pro Scan
- **Datenquellen:** DexScreener, Pump.fun Memes

### 2. Early Pump Detector ✅
- Erkennt frühe Pump-Signale
- **Bedingungen:**
  - Liquidität > $10k
  - Volume Surge > 300%
  - Buys > Sells
  - Price Change 1m > 3%

### 3. Momentum Analyzer ✅
- Signal Score Berechnung (0-100)
- **Signal-Typen:** VOLUME_SURGE, BUY_PRESSURE, WALLET_GROWTH, PRICE_ACCELERATION
- **Stärken:** STRONG, MEDIUM, WEAK, NONE

### 4. Smart Wallet Tracker ✅
- Wallet-Verfolgung für Copy-Trading
- Add/Remove/List Wallets
- Copy-Trade Signale

### 5. Trade Monitor ✅
- **Intervall:** 3 Sekunden
- Live P&L Berechnung
- Auto-Close bei TP/SL

### 6. Risk Manager ✅
- **Max Open Trades:** 20
- **Take Profit:** 10%
- **Stop Loss:** 6%
- **Daily Loss Limit:** 15%
- **Loss Streak Limit:** 5

### 7. API Failover ✅
- **Primär:** DexScreener
- **Fallback:** Birdeye, Jupiter
- Auto-Switch bei Ausfall

### 8. Crash Recovery ✅
- State Persistence in MongoDB
- Auto-Recovery nach Neustart
- Trade Recovery

---

## API Endpoints

### Auto-Trading
| Endpoint | Beschreibung |
|----------|-------------|
| `POST /api/auto-trading/start` | Bot starten |
| `POST /api/auto-trading/stop` | Bot stoppen |
| `POST /api/auto-trading/force-restart` | Force Neustart |
| `POST /api/auto-trading/reset` | State Reset |
| `GET /api/auto-trading/status` | Status & Metriken |

### Smart Wallets
| Endpoint | Beschreibung |
|----------|-------------|
| `POST /api/smart-wallets` | Wallet hinzufügen |
| `GET /api/smart-wallets` | Wallets auflisten |
| `DELETE /api/smart-wallets/{address}` | Wallet entfernen |
| `GET /api/smart-wallets/copy-signals` | Copy-Trade Signale |

### System
| Endpoint | Beschreibung |
|----------|-------------|
| `GET /api/wallet/status` | **NEU** - Wallet-Sync-Status (Frontend-Poll) |
| `GET /api/wallet/can-trade` | Prüft ob Trading möglich ist |
| `GET /api/wallet/diagnostics` | Detaillierte Wallet-Diagnose |
| `POST /api/wallet/sync` | Wallet mit Engine synchronisieren |
| `GET /api/system/modules` | Module Status |
| `GET /api/api-status` | API Failover Status |
| `POST /api/bot/save-state` | State speichern |
| `GET /api/bot/recover-state` | State laden |
| `GET /api/activity` | Activity Feed |

---

## UI Features (Deutsch)

### Dashboard
- **TESTMODUS** Toggle
- **Auto-Trading starten/stoppen** Button
- **Aktive Trades** Panel mit Live P&L
- **BOT AKTIVITÄT** Live Feed
- **Token Scanner** mit 23+ Tokens
- **Geschlossene Trades** Historie

### Statistiken
- VERFÜGBAR: SOL Budget
- IN TRADES: Investiert
- GESAMT P&L: Gesamtgewinn
- TREFFERQUOTE: Win Rate

---

## Test-Ergebnisse

- **Backend Tests:** 99/99 bestanden (100%)
- **Frontend E2E Tests:** 41+ bestanden (100%)
- **Alle Module:** Verifiziert und funktional

---

## Credentials

- **PIN:** 1234

---

## Nächste Schritte (P1)

1. **Performance Dashboard** - Top profitable Tokens, Profit/Tag
2. **UI für Smart Wallet Tracking** - Panel zum Verwalten
3. **Enhanced Token Discovery** - Mehr Datenquellen

## Zukünftige Features (P2)

1. **Ultra-Fast Sniper** - Block-Level Events
2. **MEV Protection** - Sandwich-Attack Schutz
3. **Telegram Notifications** - Alert System
4. **Jupiter Swap Integration** - Live Trading
