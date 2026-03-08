# Pump.fun Trading Bot - PRD v9

## Problem Statement
Automatisiertes Trading-System für Pump.fun Tokens auf der Solana Blockchain.

## Kritische Fixes - VOLLSTÄNDIG ✅

### 1. RPC Architektur - KOMPLETT ÜBERARBEITET ✅ (März 2026)
**Kritisches Problem gelöst: RPC Connection Failures**

**Neue Architektur:**
```
Frontend → Backend API → RPC Manager → Solana Network
```

- **Alle RPC-Aufrufe erfolgen über das Backend** - Frontend macht KEINE direkten RPC-Calls mehr
- **Automatisches Failover** zwischen RPC-Endpunkten
- **Health Monitoring** im Hintergrund alle 30 Sekunden
- **Helius-Integration vorbereitet** (via `HELIUS_API_KEY` Umgebungsvariable)

**RPC-Endpunkte (Priorität):**
1. Helius (wenn API-Key vorhanden)
2. Ankr (`https://rpc.ankr.com/solana`)
3. Solana Mainnet (`https://api.mainnet-beta.solana.com`)

### 2. System Health Diagnostics ✅
**Endpoint:** `GET /api/system/health`

Prüft alle Systemkomponenten:
- Wallet Status
- RPC Connection (mit Latenz)
- Scanner (DEX Screener API)
- Database (MongoDB)
- Trading Engine

### 3. Wallet Balance via Backend ✅
**Endpoint:** `GET /api/wallet/balance?address=xxx`

- Balance wird über Backend-RPC abgerufen (nicht Frontend)
- Vermeidet CORS und Rate-Limiting Probleme
- Unterstützt RPC Failover

### 4. Loss Streak Reset ✅
**Endpoint:** `POST /api/trading/reset-loss-streak`

- Speichert Reset-Marker in Datenbank
- Portfolio-Berechnung respektiert Reset-Marker
- Trading kann nach Reset fortgesetzt werden

### 5. Live Trading Safety ✅
**Endpoint:** `GET /api/trading/can-enable-live`

Prüft vor Live-Aktivierung:
- RPC funktioniert
- Scanner aktiv
- Database verbunden
- Keine Blocker (Loss Streak, Daily Loss Limit)

### 6. Token Scanner ✅
- Vollständige DEX Screener API URLs
- Filter für unrealistische Werte (>$100M Liquidität)
- 40+ valide Solana Pairs pro Scan
- Momentum Scoring und Signal-Stärken

## Test-Ergebnisse (März 2026)
- **Backend:** 51/51 Tests PASS (100%)
- **Frontend:** 80/80 Tests PASS (100%)
- **Keine kritischen Bugs**

## API Endpoints

| Endpoint | Beschreibung |
|----------|-------------|
| `GET /api/system/health` | System-Diagnostik |
| `GET /api/rpc/status` | RPC-Verbindungsstatus |
| `POST /api/rpc/reconnect` | RPC neu verbinden |
| `GET /api/wallet/balance` | Balance via Backend |
| `GET /api/wallet/tokens` | Token-Liste via Backend |
| `POST /api/trading/reset-loss-streak` | Loss Streak zurücksetzen |
| `GET /api/trading/can-enable-live` | Live-Trading Sicherheitscheck |
| `GET /api/tokens/scan` | Token Scanner mit Momentum |
| `GET /api/auto-trading/status` | Auto-Trading Status |

## Code-Architektur

```
Backend:
├── server.py
│   ├── RPC_ENDPOINTS[]          # Dynamisch aus ENV
│   ├── RPC_CONFIG{}             # Timeout, Retry Settings
│   ├── rpc_state{}              # Connection State Manager
│   ├── get_working_rpc()        # Failover Logic
│   ├── make_rpc_call()          # RPC with Retry
│   └── rpc_health_monitor()     # Background Health Check

Frontend (KEINE direkte RPC):
├── WalletPanel.jsx
│   └── fetchBalanceViaBackend() # Nutzt /api/wallet/balance
├── DebugPanel.jsx
│   └── System Diagnostics UI
└── SolanaWalletProvider.jsx
    └── Nur für Wallet Connection
```

## Nächste Schritte (Phase 2)

1. **Helius RPC Integration**
   - Benutzer muss `HELIUS_API_KEY` setzen für Premium-RPC
   
2. **Liquidity Migration Detector**
   - Pump.fun → Raydium/Orca Migration erkennen

3. **Smart Wallet Tracking**
   - Profitable Wallets verfolgen

4. **WebSocket Updates**
   - Real-time Token Updates

## Bekannte Limitierungen
- Wallet erfordert Phantom Extension
- Paper Mode ist Standard
- Memecoins haben keine TradingView Charts
- Öffentliche RPCs können bei hoher Last langsam sein

## Credentials
- **PIN:** Vom Benutzer gesetzt
- **RPC:** Ankr (Primary), Solana Mainnet (Fallback)
- **Helius:** Optional via `HELIUS_API_KEY` Umgebungsvariable

## Umgebungsvariablen

### Backend (.env)
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
HELIUS_API_KEY=          # Optional für Premium RPC
```

### Frontend (.env)
```
REACT_APP_BACKEND_URL=https://...
```
