# Pump.fun Trading Bot - PRD v21

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain mit vollständiger deutscher Benutzeroberfläche.

## System Status: ⚡ ULTRA-FAST SNIPER BOT AKTIV ⚡

Letztes Update: 2026-03-09

---

## Changelog (2026-03-09)

### Ultra-Fast Sniper Bot (Latest)
- **Scan-Intervall:** 0.8 Sekunden (sub-second)
- **Max Parallel Trades:** 100 (vorher 20)
- **Micro-Trade Sizing:** 0.5% des Wallets (0.005-0.05 SOL)
- **Token Age Bonus:**
  - < 60s: +60 Priority
  - < 120s: +40 Priority
  - < 5min: +20 Priority
- **Momentum Score v2:**
  ```
  score = vol_growth*0.30 + buyers*0.25 + price_1m*0.20 + accel*0.15 + age*0.10
  ```
- **Logging:**
  ```
  ⚡ SNIPER LOOP | tokens_scanned: 149 | opportunities: 27 | new_tokens: 0 | open_trades: 10 | slots_left: 90
  🔥 TOP MOMENTUM | 1. 🆕memeless score=125 (45s) | 2. Mirabel score=90 (5m)
  ⚡ TRADE EXECUTED | 🆕token: MEME | trade_size: 0.015 SOL | score=85 | age=30s | target_profit: 8%
  ```

### Sniper Exit Strategy
- **take_profit_percent:** 8% (vorher 10%)
- **stop_loss_percent:** 6%
- **trailing_stop_percent:** 4%
- **signal_cooldown:** 45 Sekunden

### Scanner Scale-Up
- **Kapazität:** 1500 Tokens pro Scan
- **7 DEX-Quellen:** parallel via asyncio.gather()

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
