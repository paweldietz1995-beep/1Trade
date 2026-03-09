# Pump.fun Trading Bot - PRD v23

## Problem Statement
Automatisiertes High-Frequency Trading-System für Pump.fun Tokens auf der Solana Blockchain mit vollständiger deutscher Benutzeroberfläche.

## System Status: HIGH-FREQUENCY MOMENTUM SCALPER V3 AKTIV

Letztes Update: 2026-03-09

---

## Changelog

### 2026-03-09 - High-Performance Scanner V3
- **NEU:** Scanner V3 implementiert mit:
  - Parallele Datenabfrage (asyncio.gather für 7 Quellen)
  - 2-Sekunden Cache für API-Antworten
  - Batch Processing (200er Chunks)
  - Token-Deduplizierung nach Adresse
  - Performance Logging

### Scanner V3 Performance Metriken:
```
sources_scanned: 7
raw_tokens: ~300
tokens_after_dedup: ~200-250
scan_time: 1.0-1.6 seconds
cache_hit_rate: ~30-50% (bei wiederholten Scans)
```

### API Endpunkte (NEU):
- `GET /api/scanner/stats` - Scanner V3 Statistiken
- `POST /api/scanner/clear-cache` - Cache leeren

---

## Implementierte Features

### 1. Scanner V3 (HIGH-PERFORMANCE)
- **7 Datenquellen:** DexScreener, Birdeye-style, Jupiter, Raydium, Orca, Meteora, Pump.fun
- **Parallele Ausführung:** asyncio.gather für alle Quellen
- **Caching:** 2-Sekunden TTL für Rate-Limit-Schutz
- **Batch Processing:** 200 Tokens pro Batch
- **Ziel:** 1000-5000 Tokens pro Zyklus in < 1.2s

### 2. Momentum Scoring V2
```
score = (volume_growth * 0.35) + (buyers_1m * 0.25) + (price_1m * 0.20) + (accel * 0.20)
```

### 3. New Token Priority:
- Token < 60s: +50 Bonus
- Token < 120s: +30 Bonus
- Token < 5min: +15 Bonus

### 4. Trading Konfiguration:
- **Take Profit:** 10%
- **Stop Loss:** 7%
- **Trailing Stop:** 4%
- **Max Parallel Trades:** 30
- **Scan Intervall:** 1.0s

---

## Module Status

| Modul | Status | Beschreibung |
|-------|--------|--------------|
| Scanner V3 | AKTIV | High-Performance Multi-Source Scanner |
| Momentum Analyzer | AKTIV | Echtzeit-Momentum-Bewertung |
| Trade Monitor | AKTIV | Live P&L Tracking |
| Risk Manager | AKTIV | TP/SL/Trailing Stop |
| API Failover | AKTIV | Auto-Switch bei Ausfall |
| Crash Recovery | AKTIV | State Persistence |
| Smart Wallet Tracker | AKTIV | Copy-Trading |

---

## API Endpoints

### Scanner
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/scanner/stats` | Scanner V3 Statistiken |
| `POST /api/scanner/clear-cache` | Cache leeren |
| `GET /api/tokens/scan` | Token-Liste abrufen |

### Auto-Trading
| Endpoint | Beschreibung |
|----------|--------------|
| `POST /api/auto-trading/start` | Bot starten |
| `POST /api/auto-trading/stop` | Bot stoppen |
| `GET /api/auto-trading/status` | Status & Metriken |

### System
| Endpoint | Beschreibung |
|----------|--------------|
| `GET /api/health` | Gesundheitscheck |
| `GET /api/wallet/status` | Wallet-Status |
| `GET /api/opportunities` | Trading-Möglichkeiten |

---

## Test-Ergebnisse

- **Backend Tests:** 74/77 bestanden (96%)
- **Frontend E2E Tests:** 37 bestanden (100%)
- **Scanner V3 Tests:** Alle bestanden

---

## Bekannte Einschränkungen

1. **API Rate Limits:** DexScreener gibt 429 bei zu vielen Anfragen
2. **Birdeye API:** Benötigt API-Key (wird durch DexScreener-Alternative ersetzt)
3. **Jupiter Token List:** Sehr groß, wird auf 300 Tokens begrenzt

---

## Nächste Schritte (P1)

1. **Realtime Launch Sniper** - Pump.fun / Raydium Pool Detection
2. **Performance Dashboard** - Top profitable Tokens, Profit/Tag
3. **UI für Smart Wallet Tracking** - Panel zum Verwalten

## Zukünftige Features (P2)

1. **MEV Protection** - Sandwich-Attack Schutz
2. **Telegram Notifications** - Alert System
3. **Jupiter Swap Integration** - Live Trading

---

## Credentials

- **PIN:** 1234

---

## Architektur

```
/app/
├── backend/
│   ├── server.py       # Monolithische FastAPI-App (~6700 Zeilen)
│   │   ├── ScannerCache      # 2s TTL Cache
│   │   ├── MultiSourceScanner # V3 High-Performance Scanner
│   │   ├── auto_trading_loop  # HFT Trading Loop
│   │   └── calculate_momentum_score_v2
│   └── tests/
│       ├── test_scanner_v3.py
│       └── test_api.py
├── frontend/
│   └── src/
│       ├── pages/Dashboard.jsx
│       └── components/scanner/TokenScanner.jsx
└── tests/
    └── e2e/
        ├── scanner-v3.spec.ts
        └── core-flows.spec.ts
```
