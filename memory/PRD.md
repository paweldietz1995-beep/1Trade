# Pump.fun Trading Bot - PRD v6

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain mit Wallet-Integration, Live-Trading, Paper-Modus und 24/7 Auto-Trading Engine.

## Phase 1 - Abgeschlossen ✅

### 1. Auto Trading Engine (3s Intervall)
- **Backend Loop:** Asynchroner Background-Task mit 3-Sekunden-Zyklus
- **Endpoints:**
  - `POST /api/auto-trading/start` - Engine starten
  - `POST /api/auto-trading/stop` - Engine stoppen
  - `GET /api/auto-trading/status` - Status abrufen
  - `GET /api/auto-trading/opportunities` - Aktuelle Signale

- **Workflow pro Zyklus:**
  1. Token-Scan (DEX Screener + Pump.fun)
  2. Filter anwenden (Liquidität > $5000, Volumen > $10000)
  3. Risk Analysis durchführen
  4. Momentum Signals berechnen
  5. Bei starkem Signal → Trade ausführen

### 2. Enhanced Momentum Detection
Vier Signal-Typen implementiert:

| Signal | Threshold | Beschreibung |
|--------|-----------|--------------|
| VOLUME_SURGE | +150% | 5min Volumen vs. 1h Durchschnitt |
| BUY_PRESSURE | 30 Käufer + 1.5x Ratio | Käufer in 5min + Buy/Sell Ratio |
| WALLET_GROWTH | +100% | Neue Wallet-Käufer vs. Durchschnitt |
| PRICE_ACCELERATION | +5% + 2% über Trend | Preis-Beschleunigung in 5min |

**BUY Signal:** Mindestens 2 starke Signale + Momentum Score ≥ 70

### 3. Debug Monitoring Panel
Neues Panel zeigt:
- Wallet Status (Connected/Disconnected)
- RPC Status (Endpoint, Latenz)
- Backend Status (Healthy, Version)
- Auto Trading Status (Active, Scans, Trades)
- Activity Log (Echtzeit)

### 4. Strengere Token-Filter
- Min. Liquidität: **$5,000** (vorher $1,000)
- Min. Volumen 24h: **$10,000** (vorher $1,000)
- Min. Momentum Score: **70** (für Auto-Trade)
- Min. Käufer 5min: **30**
- Max. Token-Alter: **24 Stunden**

## Test-Ergebnisse Phase 1
- **Backend:** 31/31 Tests PASS (100%)
- **Frontend:** 71/76 Tests PASS (93%)
- **Keine kritischen Bugs**

## Code-Architektur

```
Backend (/app/backend/server.py):
├── Auto Trading Engine
│   ├── auto_trading_state (Global State)
│   ├── auto_trading_loop() (Background Task)
│   └── execute_auto_trade_cycle() (Pro Zyklus)
├── Enhanced Momentum Detection
│   └── calculate_enhanced_momentum() (4 Signal-Typen)
└── API Endpoints (41 total)

Frontend:
├── /app/frontend/src/pages/Dashboard.jsx (Hauptansicht)
├── /app/frontend/src/components/DebugPanel.jsx (NEU)
└── /app/frontend/src/services/jupiterService.js (Live Trades)
```

## Phase 2 - Ausstehend 🔜

### 1. Liquidity Migration Detector
- Erkennung von Pump.fun → Raydium/Orca Migration
- Automatisches Signal bei Migration

### 2. Smart Wallet Tracking
- Profitable Wallets tracken
- Signal verstärken bei Smart Wallet Aktivität

### 3. Performance-Optimierungen
- WebSocket für Real-time Updates
- RPC Latenz-Monitoring

## Phase 3 - Backlog 📋

- Ultra-Fast Sniper Module
- MEV/Sandwich Protection
- Telegram Bot Integration
- Multi-Wallet Support
- Copy-Trading Feature
- AI Trading Models

## API Endpoints (Komplett)

| Kategorie | Endpoint | Beschreibung |
|-----------|----------|--------------|
| **Auth** | POST /api/auth/login | PIN-Login |
| **Auto Trading** | POST /api/auto-trading/start | Engine starten |
| | POST /api/auto-trading/stop | Engine stoppen |
| | GET /api/auto-trading/status | Status |
| | GET /api/auto-trading/opportunities | Signale |
| **Portfolio** | GET /api/portfolio | Übersicht |
| **Settings** | GET /api/bot/settings | Einstellungen |
| | PUT /api/bot/settings | Aktualisieren |
| **Tokens** | GET /api/tokens/scan | Scanner |
| | GET /api/tokens/{address} | Details |
| **Trades** | POST /api/trades | Erstellen |
| | GET /api/trades | Liste |
| | PUT /api/trades/{id}/close | Schließen |
| **Market** | GET /api/market/sol-price | SOL Preis |
| | GET /api/market/trending | Trending |

## Credentials
- **PIN:** Vom Benutzer gesetzt
- **RPC:** Ankr (Primary), Solana Mainnet (Fallback)
- **Jupiter API:** Keine Keys erforderlich

## Bekannte Limitierungen
- Wallet-Verbindung erfordert Phantom Extension
- Rate Limiting bei schnellen API-Calls möglich
- Paper Mode ist Standard (Live erfordert Bestätigung)
